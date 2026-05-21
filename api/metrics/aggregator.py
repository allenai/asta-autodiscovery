"""GCS data aggregation and caching for the metrics dashboard.

Scans all users and jobs in GCS to build an in-memory cache of job snapshots.
Uses a stale-while-revalidate pattern with background refresh.
Incremental scanning skips terminal jobs that are already cached.

The cache is persisted to GCS so pod restarts don't trigger a full rescan.
"""

from __future__ import annotations

import dataclasses
import fcntl
import json
import logging
import os
import statistics
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from autodiscovery_jobs.config import JobConfig
from google.cloud import storage

from .costs import _lookup_pricing, calculate_llm_cost, get_duration_seconds
from .models import (
    AggregatedUsageBucket,
    AggregatedUsageResponse,
    DailyMetrics,
    OverviewMetrics,
    RunSummary,
    UserDetailMetrics,
    UserMetricsSummary,
)

logger = logging.getLogger(__name__)

# Statuses that indicate a run was "attempted" (not just created)
STARTED_STATUSES = {"PENDING", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"}
TERMINAL_STATUSES = {"SUCCEEDED", "FAILED", "CANCELLED", "DELETED"}
# Historical runs may use either root filename; both are non-experiment init nodes.
ROOT_NODE_FILENAMES = {"mcts_node_0_0.json", "mcts_node_1_0.json"}

# Where the persisted metrics cache snapshot lives in the shared GCS bucket.
# Loaded on cold start so pod restarts don't re-scan every job from scratch.
PERSIST_BLOB_PATH = "_metrics/jobs_cache.json"
PERSIST_SCHEMA_VERSION = 1

# Per-pod file lock so only one gunicorn worker scans GCS at a time. Other
# workers wait for the persisted blob and pick it up via warm-start.
SCAN_LOCK_PATH = "/tmp/asta_metrics_scan.lock"


@dataclass
class JobSnapshot:
    """Cached snapshot of a single job's key metrics."""

    userid: str
    jobid: str
    status: str
    created_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    is_shared: bool = False
    name: str | None = None
    domain: str | None = None
    n_experiments_requested: int = 0
    n_experiments_completed: int = 0
    model: str | None = None
    llm_usage_summary: dict | None = None
    llm_cost_usd: float = 0.0
    llm_cost_by_agent: dict[str, dict[str, float]] = field(default_factory=dict)
    llm_cost_by_component: dict[str, dict[str, float]] = field(default_factory=dict)
    llm_cost_by_node: dict[str, dict[str, float]] = field(default_factory=dict)


@dataclass
class AggregatedData:
    """Full cache of all job snapshots."""

    jobs: list[JobSnapshot] = field(default_factory=list)
    refreshed_at: str | None = None
    scan_duration_seconds: float = 0.0


# ---------------------------------------------------------------------------
# GCS helpers
# ---------------------------------------------------------------------------

def _read_gcs_json(bucket: storage.Bucket, blob_path: str) -> dict | None:
    """Read and parse a JSON file from GCS. Returns None on any error."""
    try:
        blob = bucket.blob(blob_path)
        content = blob.download_as_text()
        return json.loads(content)
    except Exception:
        return None


def _read_gcs_jsonl(bucket: storage.Bucket, blob_path: str) -> list[dict[str, Any]]:
    """Read and parse a JSONL file from GCS. Returns [] on any error."""
    try:
        blob = bucket.blob(blob_path)
        content = blob.download_as_text()
    except Exception:
        return []

    events: list[dict[str, Any]] = []
    for line in content.splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            parsed = json.loads(text)
        except Exception:
            continue
        if isinstance(parsed, dict):
            events.append(parsed)
    return events


def _save_persisted_cache(bucket: storage.Bucket, data: AggregatedData) -> None:
    """Write the aggregated cache to GCS so future pods can warm-start from it."""
    try:
        payload = {
            "schema_version": PERSIST_SCHEMA_VERSION,
            "refreshed_at": data.refreshed_at,
            "scan_duration_seconds": data.scan_duration_seconds,
            "jobs": [dataclasses.asdict(j) for j in data.jobs],
        }
        blob = bucket.blob(PERSIST_BLOB_PATH)
        blob.upload_from_string(json.dumps(payload), content_type="application/json")
        logger.warning(
            f"Persisted metrics cache: {len(data.jobs)} jobs to gs://{bucket.name}/{PERSIST_BLOB_PATH}"
        )
    except Exception as e:
        logger.warning(f"Failed to persist metrics cache: {e}")


def _load_persisted_cache(bucket: storage.Bucket) -> AggregatedData | None:
    """Load the persisted cache from GCS. Returns None if absent or unreadable."""
    try:
        blob = bucket.blob(PERSIST_BLOB_PATH)
        content = blob.download_as_text()
    except Exception:
        return None

    try:
        payload = json.loads(content)
    except Exception as e:
        logger.warning(f"Persisted metrics cache is not valid JSON: {e}")
        return None

    if payload.get("schema_version") != PERSIST_SCHEMA_VERSION:
        logger.info(
            f"Ignoring persisted cache with schema_version={payload.get('schema_version')} "
            f"(expected {PERSIST_SCHEMA_VERSION}); will rebuild."
        )
        return None

    jobs: list[JobSnapshot] = []
    for raw in payload.get("jobs", []):
        try:
            jobs.append(JobSnapshot(**raw))
        except TypeError:
            # Drop snapshots that don't match the current dataclass shape; the
            # incremental rescan will rebuild them.
            continue

    return AggregatedData(
        jobs=jobs,
        refreshed_at=payload.get("refreshed_at"),
        scan_duration_seconds=float(payload.get("scan_duration_seconds") or 0.0),
    )


def _coerce_nonnegative_int(value: object) -> int:
    """Parse a value into a non-negative int, returning 0 on invalid input."""
    try:
        return max(0, int(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _lookup_bucket_cost_by_type(model_name: str, bucket: dict[str, Any]) -> tuple[float, float, float]:
    """Calculate prompt/completion/reasoning costs for one usage bucket."""
    pricing = _lookup_pricing(model_name)

    prompt_tokens = _coerce_nonnegative_int(bucket.get("prompt_tokens"))
    completion_tokens = _coerce_nonnegative_int(bucket.get("completion_tokens"))
    reasoning_tokens = _coerce_nonnegative_int(bucket.get("reasoning_tokens"))
    total_tokens = _coerce_nonnegative_int(bucket.get("total_tokens"))

    output_tokens = max(0, total_tokens - prompt_tokens)
    prompt_cost = (prompt_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]

    explicit_output_tokens = completion_tokens + reasoning_tokens
    if explicit_output_tokens > 0:
        completion_cost = output_cost * (completion_tokens / explicit_output_tokens)
        reasoning_cost = output_cost * (reasoning_tokens / explicit_output_tokens)
    else:
        completion_cost = output_cost
        reasoning_cost = 0.0

    return prompt_cost, completion_cost, reasoning_cost


def _extract_event_bucket(event: dict[str, Any]) -> dict[str, int]:
    """Extract normalized token counts from one usage event."""
    usage = event.get("usage") if isinstance(event.get("usage"), dict) else {}
    usage = usage if isinstance(usage, dict) else {}

    prompt_tokens = _coerce_nonnegative_int(usage.get("prompt_tokens"))
    completion_tokens = _coerce_nonnegative_int(usage.get("completion_tokens"))
    total_tokens = _coerce_nonnegative_int(usage.get("total_tokens"))
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens

    completion_details = (
        usage.get("completion_tokens_details")
        if isinstance(usage.get("completion_tokens_details"), dict)
        else {}
    )
    completion_details = completion_details if isinstance(completion_details, dict) else {}
    reasoning_tokens = _coerce_nonnegative_int(completion_details.get("reasoning_tokens"))
    if reasoning_tokens == 0:
        reasoning_tokens = _coerce_nonnegative_int(usage.get("reasoning_tokens"))

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


def _empty_cost_bucket() -> dict[str, float]:
    """Return an empty cost bucket."""
    return {
        "prompt_cost_usd": 0.0,
        "completion_cost_usd": 0.0,
        "reasoning_cost_usd": 0.0,
        "total_cost_usd": 0.0,
    }


def _accumulate_cost(
    target: dict[str, dict[str, float]],
    key: str,
    prompt_cost: float,
    completion_cost: float,
    reasoning_cost: float,
) -> None:
    """Accumulate one usage event cost into a keyed cost map."""
    bucket = target.setdefault(key, _empty_cost_bucket())
    bucket["prompt_cost_usd"] += prompt_cost
    bucket["completion_cost_usd"] += completion_cost
    bucket["reasoning_cost_usd"] += reasoning_cost
    bucket["total_cost_usd"] += prompt_cost + completion_cost + reasoning_cost


def _build_event_cost_breakdowns(
    events: list[dict[str, Any]],
) -> tuple[
    dict[str, dict[str, float]],
    dict[str, dict[str, float]],
    dict[str, dict[str, float]],
]:
    """Build exact cost maps from raw usage events by agent/component/node."""
    by_agent: dict[str, dict[str, float]] = {}
    by_component: dict[str, dict[str, float]] = {}
    by_node: dict[str, dict[str, float]] = {}

    for event in events:
        model = str(event.get("model") or "unknown")
        bucket = _extract_event_bucket(event)
        prompt_cost, completion_cost, reasoning_cost = _lookup_bucket_cost_by_type(model, bucket)

        agent_key = str(event.get("agent_name") or "unassigned")
        component_key = str(event.get("component") or "unknown")
        node_key = str(event.get("node_id") or "run_level")

        _accumulate_cost(by_agent, agent_key, prompt_cost, completion_cost, reasoning_cost)
        _accumulate_cost(by_component, component_key, prompt_cost, completion_cost, reasoning_cost)
        _accumulate_cost(by_node, node_key, prompt_cost, completion_cost, reasoning_cost)

    return by_agent, by_component, by_node


def _derive_requested_experiments(
    metadata: dict | None,
    run_args: dict | None,
) -> int:
    """Derive requested experiment count from metadata and args.

    Includes warmstart experiments so requested/completed are measured on
    the same basis.
    """
    metadata = metadata or {}
    run_args = run_args or {}

    requested_main = _coerce_nonnegative_int(
        metadata.get("n_experiments") or run_args.get("n_experiments"),
    )
    requested_warmstart = _coerce_nonnegative_int(
        metadata.get("n_warmstart") or run_args.get("n_warmstart"),
    )
    return requested_main + requested_warmstart


# ---------------------------------------------------------------------------
# Job scanning
# ---------------------------------------------------------------------------

def _count_experiments_inline(
    bucket: storage.Bucket,
    userid: str,
    jobid: str,
) -> int:
    """Count completed experiment result files using match_glob on the shared bucket.

    Excludes the root initialisation node (legacy filename variants),
    which is not a real experiment.
    """
    try:
        blobs = bucket.list_blobs(
            match_glob=f"users/{userid}/jobs/{jobid}/output/mcts_node_*_*.json",
        )
        return sum(
            1
            for b in blobs
            if b.name.rsplit("/", 1)[-1] not in ROOT_NODE_FILENAMES
        )
    except Exception:
        return 0


def _infer_model(llm_summary: dict | None) -> str | None:
    """Infer the primary model name from llm_usage_summary by_model keys."""
    if not llm_summary:
        return None
    by_model = llm_summary.get("by_model", {})
    if not by_model:
        return None
    # Return the model with the most total tokens
    return max(by_model, key=lambda k: by_model[k].get("total_tokens", 0))


def _scan_job(
    userid: str,
    jobid: str,
    bucket: storage.Bucket,
) -> JobSnapshot | None:
    """Scan a single job and build a snapshot. Returns None on critical failure."""
    try:
        base_path = f"users/{userid}/jobs/{jobid}"

        # Read run_details.json
        run_details = _read_gcs_json(bucket, f"{base_path}/run_details.json")
        if not run_details:
            return None

        status = run_details.get("status", "UNKNOWN")
        created_at = run_details.get("created_at")
        finished_at = run_details.get("finished_at")
        duration = get_duration_seconds(created_at, finished_at)

        # Read metadata.json
        metadata = _read_gcs_json(bucket, f"{base_path}/metadata.json")
        is_shared = bool(metadata.get("is_shared")) if metadata else False
        name = metadata.get("name") if metadata else None
        domain = metadata.get("domain") if metadata else None
        # Read output/args.json as fallback for legacy runs where metadata.json
        # is missing or incomplete.
        run_args = _read_gcs_json(bucket, f"{base_path}/output/args.json")
        n_requested = _derive_requested_experiments(metadata, run_args)

        # Count completed experiments using shared bucket
        n_completed_raw = _count_experiments_inline(bucket, userid, jobid)
        if n_requested == 0 and n_completed_raw > 0:
            # Legacy/partial runs may be missing requested counts in both metadata
            # and args. Use completed as a floor so aggregates remain consistent.
            n_requested = n_completed_raw
        n_completed = min(n_completed_raw, n_requested)

        # Read LLM usage summary
        llm_summary = _read_gcs_json(bucket, f"{base_path}/output/llm_usage_summary.json")
        llm_events = _read_gcs_jsonl(bucket, f"{base_path}/output/llm_usage_events.jsonl")

        # Calculate LLM cost and infer model from usage data
        llm_cost = 0.0
        if llm_summary:
            llm_cost, _ = calculate_llm_cost(llm_summary)
        model = _infer_model(llm_summary)
        llm_cost_by_agent, llm_cost_by_component, llm_cost_by_node = _build_event_cost_breakdowns(
            llm_events
        )

        return JobSnapshot(
            userid=userid,
            jobid=jobid,
            status=status,
            created_at=created_at,
            finished_at=finished_at,
            duration_seconds=duration,
            is_shared=is_shared,
            name=name,
            domain=domain,
            n_experiments_requested=n_requested,
            n_experiments_completed=n_completed,
            model=model,
            llm_usage_summary=llm_summary,
            llm_cost_usd=llm_cost,
            llm_cost_by_agent=llm_cost_by_agent,
            llm_cost_by_component=llm_cost_by_component,
            llm_cost_by_node=llm_cost_by_node,
        )
    except Exception as e:
        logger.warning(f"Failed to scan job {userid}/{jobid}: {e}")
        return None


def _discover_jobs_via_glob(
    bucket: storage.Bucket,
) -> list[tuple[str, str]]:
    """Discover all (userid, jobid) pairs with a single glob API call."""
    job_keys: list[tuple[str, str]] = []
    blobs = bucket.list_blobs(match_glob="users/*/jobs/*/run_details.json")
    for blob in blobs:
        # blob.name: "users/{userid}/jobs/{jobid}/run_details.json"
        parts = blob.name.split("/")
        if len(parts) >= 4:
            job_keys.append((parts[1], parts[3]))
    return job_keys


def _scan_all_jobs(
    config: JobConfig,
    previous: AggregatedData | None = None,
) -> AggregatedData:
    """Scan all users and jobs in GCS to build the aggregated data.

    Uses glob-based discovery (single API call) and a global thread pool
    for parallel scanning. Terminal jobs from a previous scan are carried
    forward without re-reading from GCS.
    """
    start_time = time.monotonic()
    client = storage.Client(project=config.project_id)
    bucket = client.bucket(config.bucket)

    # Build index of previously-cached terminal jobs to skip re-scanning.
    cached_terminal: dict[tuple[str, str], JobSnapshot] = {}
    if previous:
        for j in previous.jobs:
            if j.status in TERMINAL_STATUSES:
                # Self-heal stale bad snapshots by forcing a rescan when completed > requested.
                if (
                    j.n_experiments_requested > 0
                    and j.n_experiments_completed > j.n_experiments_requested
                ):
                    continue
                # Force one-time re-scan when older cached snapshots predate
                # exact event-level cost attribution fields.
                if not hasattr(j, "llm_cost_by_agent"):
                    continue
                cached_terminal[(j.userid, j.jobid)] = j

    # Discover all jobs in one glob call
    try:
        all_job_keys = _discover_jobs_via_glob(bucket)
    except Exception as e:
        logger.error(f"Failed to discover jobs via glob: {e}")
        return AggregatedData(
            refreshed_at=datetime.now(UTC).isoformat(),
            scan_duration_seconds=time.monotonic() - start_time,
        )

    # Separate into cached (skip) and need-to-scan
    all_snapshots: list[JobSnapshot] = []
    to_scan: list[tuple[str, str]] = []
    for key in all_job_keys:
        if key in cached_terminal:
            all_snapshots.append(cached_terminal[key])
        else:
            to_scan.append(key)
    skipped = len(all_snapshots)

    logger.warning(
        f"Metrics scan starting: {len(all_job_keys)} jobs total "
        f"(scanning {len(to_scan)}, reusing {skipped} from cache)"
    )

    # Scan all remaining jobs in a single global thread pool
    scanned = 0
    progress_lock = threading.Lock()
    last_log = [time.monotonic()]
    if to_scan:
        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = {
                executor.submit(_scan_job, userid, jobid, bucket): (userid, jobid)
                for userid, jobid in to_scan
            }
            for future in as_completed(futures):
                snapshot = future.result()
                if snapshot:
                    all_snapshots.append(snapshot)
                with progress_lock:
                    scanned += 1
                    now = time.monotonic()
                    if now - last_log[0] >= 10.0:
                        logger.warning(
                            f"Metrics scan progress: {scanned}/{len(to_scan)} jobs "
                            f"({now - start_time:.0f}s elapsed)"
                        )
                        last_log[0] = now

    unique_users = len({k[0] for k in all_job_keys})
    elapsed = time.monotonic() - start_time
    logger.warning(
        f"Metrics scan complete: {len(all_snapshots)} jobs from {unique_users} users "
        f"in {elapsed:.1f}s (scanned {scanned}, reused {skipped})"
    )

    return AggregatedData(
        jobs=all_snapshots,
        refreshed_at=datetime.now(UTC).isoformat(),
        scan_duration_seconds=elapsed,
    )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

class MetricsCache:
    """In-memory cache for aggregated metrics data with background refresh."""

    def __init__(self, refresh_interval_seconds: int = 300):
        self._lock = threading.RLock()
        self._data: AggregatedData | None = None
        self._refresh_interval = refresh_interval_seconds
        self._refreshing = False
        self._config = JobConfig()

    @property
    def is_refreshing(self) -> bool:
        with self._lock:
            return self._refreshing

    def get_data(self) -> AggregatedData:
        """Get cached data, triggering refresh if stale or empty.

        On cold start, attempts to warm-start from the GCS-persisted snapshot
        so the HTTP request never blocks on a full scan. If no persisted
        snapshot exists, returns empty data immediately and refreshes in the
        background; callers should treat ``refreshed_at is None`` as a
        "warming up" signal.

        While still warming up, re-checks GCS on each call so that as soon as
        *any* worker (in this pod or another) finishes its scan and persists
        the blob, all other workers pick it up on their next request rather
        than waiting for their own independent scan to finish.
        """
        with self._lock:
            if self._data is None:
                self._data = self._warm_start(initial=True)
                self._trigger_background_refresh()
            elif self._data.refreshed_at is None:
                warmed = self._warm_start(initial=False)
                if warmed.refreshed_at is not None:
                    self._data = warmed
                self._trigger_background_refresh()
            elif self._is_stale():
                self._trigger_background_refresh()
            return self._data

    def _warm_start(self, initial: bool) -> AggregatedData:
        """Try to populate the cache from GCS; fall back to empty.

        ``initial`` controls log verbosity: the very first attempt logs the
        outcome at WARNING so it's visible operationally; subsequent retries
        during the warming-up window are silent on the "blob still missing"
        path to avoid spamming on every poll.
        """
        try:
            client = storage.Client(project=self._config.project_id)
            bucket = client.bucket(self._config.bucket)
            loaded = _load_persisted_cache(bucket)
        except Exception as e:
            if initial:
                logger.warning(f"Warm-start load failed: {e}")
            loaded = None

        if loaded is not None:
            logger.warning(
                f"Warm-started metrics cache from GCS: {len(loaded.jobs)} jobs "
                f"(refreshed_at={loaded.refreshed_at})"
            )
            return loaded

        if initial:
            logger.warning(
                "No persisted metrics cache found; serving empty while background scan runs."
            )
        return AggregatedData()

    def force_refresh(self) -> None:
        """Force a background refresh regardless of staleness."""
        self._trigger_background_refresh()

    def _is_stale(self) -> bool:
        if not self._data or not self._data.refreshed_at:
            return True
        try:
            refreshed = datetime.fromisoformat(self._data.refreshed_at)
            age = (datetime.now(UTC) - refreshed).total_seconds()
            return age > self._refresh_interval
        except (ValueError, TypeError):
            return True

    def _trigger_background_refresh(self) -> None:
        with self._lock:
            if self._refreshing:
                return
            self._refreshing = True
        thread = threading.Thread(target=self._background_refresh, daemon=True)
        thread.start()

    def _background_refresh(self) -> None:
        """Run a refresh, but only if no other worker on this pod is already scanning.

        Workers that lose the lock race quickly clear their in-process
        ``_refreshing`` flag and return; they'll pick up the persisted
        snapshot via warm-start as soon as the scanning worker writes it.
        """
        lock_file = None
        try:
            try:
                lock_file = open(SCAN_LOCK_PATH, "w")
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError:
                logger.warning(
                    f"Metrics scan skipped on pid={os.getpid()}: another worker holds {SCAN_LOCK_PATH}"
                )
                if lock_file is not None:
                    lock_file.close()
                lock_file = None
                return
            self._do_refresh()
        finally:
            if lock_file is not None:
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                finally:
                    lock_file.close()
            with self._lock:
                self._refreshing = False

    def _do_refresh(self) -> None:
        with self._lock:
            self._refreshing = True
        try:
            with self._lock:
                previous = self._data
            data = _scan_all_jobs(self._config, previous=previous)
            with self._lock:
                self._data = data
            try:
                client = storage.Client(project=self._config.project_id)
                bucket = client.bucket(self._config.bucket)
                _save_persisted_cache(bucket, data)
            except Exception as e:
                logger.warning(f"Failed to persist metrics cache after refresh: {e}")
        except Exception as e:
            logger.error(f"Metrics cache refresh failed: {e}")
        finally:
            with self._lock:
                self._refreshing = False


# Module-level singleton
_cache: MetricsCache | None = None
_cache_lock = threading.Lock()


def get_metrics_cache() -> MetricsCache:
    """Get or create the singleton MetricsCache."""
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:
                _cache = MetricsCache()
    return _cache


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def _filter_jobs(
    jobs: list[JobSnapshot],
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[JobSnapshot]:
    """Filter jobs by date range based on created_at."""
    if not start_date and not end_date:
        return jobs

    filtered = []
    for job in jobs:
        if not job.created_at:
            continue
        try:
            created = job.created_at[:10]  # YYYY-MM-DD
        except (IndexError, TypeError):
            continue

        if start_date and created < start_date:
            continue
        if end_date and created > end_date:
            continue
        filtered.append(job)
    return filtered


def compute_overview(
    start_date: str | None = None,
    end_date: str | None = None,
) -> OverviewMetrics:
    """Compute overview metrics from the cache."""
    cache = get_metrics_cache()
    data = cache.get_data()
    jobs = _filter_jobs(data.jobs, start_date, end_date)

    # Basic counts
    succeeded = [j for j in jobs if j.status == "SUCCEEDED"]
    failed = [j for j in jobs if j.status == "FAILED"]
    cancelled = [j for j in jobs if j.status == "CANCELLED"]

    total_terminal = len(succeeded) + len(failed)
    success_rate = len(succeeded) / total_terminal if total_terminal > 0 else 0.0

    # Unique users
    unique_users = len({j.userid for j in jobs})

    # Experiments
    total_experiments = sum(j.n_experiments_completed for j in jobs)
    total_experiments_requested = sum(j.n_experiments_requested for j in jobs)
    exp_completion_rate = (
        total_experiments / total_experiments_requested
        if total_experiments_requested > 0
        else 0.0
    )

    # LLM costs
    total_llm = sum(j.llm_cost_usd for j in jobs)

    # Cost per hypothesis — only consider jobs with LLM usage data
    jobs_with_usage = [j for j in jobs if j.llm_usage_summary]
    hypotheses_with_usage = sum(j.n_experiments_completed for j in jobs_with_usage)
    llm_cost_for_hypotheses = sum(j.llm_cost_usd for j in jobs_with_usage)
    cost_per_hypothesis = (
        llm_cost_for_hypotheses / hypotheses_with_usage
        if hypotheses_with_usage > 0
        else None
    )

    # Share rate
    shared_runs = sum(1 for j in jobs if j.is_shared)
    share_rate = shared_runs / len(jobs) if jobs else 0.0

    # Runs by status
    status_counts: dict[str, int] = defaultdict(int)
    for j in jobs:
        status_counts[j.status] += 1

    # Time series
    daily: dict[str, DailyMetrics] = {}
    daily_started_users: dict[str, set[str]] = defaultdict(set)
    for j in jobs:
        if not j.created_at:
            continue
        date = j.created_at[:10]
        if date not in daily:
            daily[date] = DailyMetrics(date=date)
        day = daily[date]
        if j.status in STARTED_STATUSES:
            day.runs_started += 1
            daily_started_users[date].add(j.userid)
        day.hypotheses_conducted += j.n_experiments_completed
        if j.status == "SUCCEEDED":
            day.runs_succeeded += 1
        if j.status == "FAILED":
            day.runs_failed += 1
        day.llm_cost_usd += j.llm_cost_usd

    # Round daily costs
    for day in daily.values():
        day.unique_users_started = len(daily_started_users.get(day.date, set()))
        day.llm_cost_usd = round(day.llm_cost_usd, 4)

    time_series = sorted(daily.values(), key=lambda d: d.date)

    return OverviewMetrics(
        total_runs=len(jobs),
        succeeded_runs=len(succeeded),
        failed_runs=len(failed),
        cancelled_runs=len(cancelled),
        success_rate=round(success_rate, 4),
        unique_users=unique_users,
        total_experiments=total_experiments,
        total_experiments_requested=total_experiments_requested,
        experiment_completion_rate=round(exp_completion_rate, 4),
        llm_cost_usd=round(total_llm, 4),
        hypotheses_with_usage=hypotheses_with_usage,
        cost_per_hypothesis_usd=round(cost_per_hypothesis, 4) if cost_per_hypothesis is not None else None,
        share_rate=round(share_rate, 4),
        runs_by_status=dict(status_counts),
        time_series=time_series,
        cache_refreshed_at=data.refreshed_at,
        is_warming_up=data.refreshed_at is None,
    )


def compute_users_list(
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[UserMetricsSummary]:
    """Compute per-user metrics summaries."""
    cache = get_metrics_cache()
    data = cache.get_data()
    jobs = _filter_jobs(data.jobs, start_date, end_date)

    users: dict[str, list[JobSnapshot]] = defaultdict(list)
    for j in jobs:
        users[j.userid].append(j)

    result = []
    for userid, user_jobs in users.items():
        started = [j for j in user_jobs if j.status in STARTED_STATUSES]
        succeeded = sum(1 for j in user_jobs if j.status == "SUCCEEDED")
        failed = sum(1 for j in user_jobs if j.status == "FAILED")
        total_started = len(started)
        sr = succeeded / total_started if total_started > 0 else 0.0

        total_experiments = sum(j.n_experiments_completed for j in user_jobs)
        total_llm = sum(j.llm_cost_usd for j in user_jobs)
        shared = sum(1 for j in user_jobs if j.is_shared)

        # Most recent activity
        dates = [j.created_at for j in user_jobs if j.created_at]
        last_activity = max(dates) if dates else None

        result.append(
            UserMetricsSummary(
                userid=userid,
                total_runs=len(user_jobs),
                succeeded_runs=succeeded,
                failed_runs=failed,
                success_rate=round(sr, 4),
                total_experiments=total_experiments,
                llm_cost_usd=round(total_llm, 4),
                shared_runs=shared,
                last_activity=last_activity,
            )
        )

    # Sort by LLM cost descending
    result.sort(key=lambda u: u.llm_cost_usd, reverse=True)
    return result


def compute_user_detail(userid: str) -> UserDetailMetrics:
    """Compute detailed metrics for a single user."""
    cache = get_metrics_cache()
    data = cache.get_data()
    user_jobs = [j for j in data.jobs if j.userid == userid]

    # Build summary
    started = [j for j in user_jobs if j.status in STARTED_STATUSES]
    succeeded = sum(1 for j in user_jobs if j.status == "SUCCEEDED")
    failed = sum(1 for j in user_jobs if j.status == "FAILED")
    total_started = len(started)
    sr = succeeded / total_started if total_started > 0 else 0.0

    total_experiments = sum(j.n_experiments_completed for j in user_jobs)
    total_llm = sum(j.llm_cost_usd for j in user_jobs)
    shared = sum(1 for j in user_jobs if j.is_shared)
    dates = [j.created_at for j in user_jobs if j.created_at]
    last_activity = max(dates) if dates else None

    summary = UserMetricsSummary(
        userid=userid,
        total_runs=len(user_jobs),
        succeeded_runs=succeeded,
        failed_runs=failed,
        success_rate=round(sr, 4),
        total_experiments=total_experiments,
        llm_cost_usd=round(total_llm, 4),
        shared_runs=shared,
        last_activity=last_activity,
    )

    # Build per-run summaries
    runs = []
    for j in user_jobs:
        runs.append(
            RunSummary(
                runid=j.jobid,
                userid=j.userid,
                status=j.status,
                name=j.name,
                domain=j.domain,
                created_at=j.created_at,
                finished_at=j.finished_at,
                duration_seconds=j.duration_seconds,
                n_experiments_requested=j.n_experiments_requested,
                n_experiments_completed=j.n_experiments_completed,
                is_shared=j.is_shared,
                model=j.model,
                llm_cost_usd=j.llm_cost_usd,
            )
        )

    # Sort runs by created_at descending
    runs.sort(key=lambda r: r.created_at or "", reverse=True)

    return UserDetailMetrics(userid=userid, summary=summary, runs=runs)


def compute_run_metrics(userid: str, runid: str) -> dict | None:
    """Compute detailed metrics for a single run.

    For per-run metrics, we use the cached snapshot for basic data
    and also return the raw LLM usage summary for the frontend dashboard.
    """
    cache = get_metrics_cache()
    data = cache.get_data()

    job = next((j for j in data.jobs if j.userid == userid and j.jobid == runid), None)
    if not job:
        return None

    # Calculate LLM cost breakdown by model
    llm_cost_by_model: dict[str, float] = {}
    if job.llm_usage_summary:
        _, llm_cost_by_model = calculate_llm_cost(job.llm_usage_summary)

    return {
        "runid": job.jobid,
        "userid": job.userid,
        "status": job.status,
        "name": job.name,
        "domain": job.domain,
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "duration_seconds": job.duration_seconds,
        "llm_usage_summary": job.llm_usage_summary,
        "llm_cost_usd": job.llm_cost_usd,
        "llm_cost_by_model": llm_cost_by_model,
        "n_experiments_requested": job.n_experiments_requested,
        "n_experiments_completed": job.n_experiments_completed,
        "is_shared": job.is_shared,
        "model": job.model,
    }


def _build_aggregated_bucket(
    per_run_tokens: list[int],
    per_run_costs: list[float],
    total_calls: int,
    total_prompt: int,
    total_completion: int,
    total_reasoning: int,
    total_tokens: int,
    total_cost: float,
    total_prompt_cost: float = 0.0,
    total_completion_cost: float = 0.0,
    total_reasoning_cost: float = 0.0,
) -> AggregatedUsageBucket:
    """Build an AggregatedUsageBucket from accumulated values."""
    n = len(per_run_tokens)
    mean_tok = statistics.mean(per_run_tokens) if n > 0 else 0.0
    std_tok = statistics.stdev(per_run_tokens) if n > 1 else 0.0
    mean_cost = statistics.mean(per_run_costs) if n > 0 else 0.0
    std_cost = statistics.stdev(per_run_costs) if n > 1 else 0.0

    return AggregatedUsageBucket(
        total_calls=total_calls,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        total_reasoning_tokens=total_reasoning,
        total_tokens=total_tokens,
        total_cost_usd=round(total_cost, 4),
        total_prompt_cost_usd=round(total_prompt_cost, 4),
        total_completion_cost_usd=round(total_completion_cost, 4),
        total_reasoning_cost_usd=round(total_reasoning_cost, 4),
        run_count=n,
        mean_tokens_per_run=round(mean_tok, 1),
        stddev_tokens_per_run=round(std_tok, 1),
        mean_cost_per_run=round(mean_cost, 6),
        stddev_cost_per_run=round(std_cost, 6),
    )


def compute_aggregated_usage(
    start_date: str | None = None,
    end_date: str | None = None,
) -> AggregatedUsageResponse:
    """Compute aggregated LLM usage across all runs with usage data."""
    cache = get_metrics_cache()
    data = cache.get_data()
    jobs = _filter_jobs(data.jobs, start_date, end_date)
    jobs_with_usage = [j for j in jobs if j.llm_usage_summary]

    if not jobs_with_usage:
        return AggregatedUsageResponse()

    def _extract_run_costs_by_type(llm_summary: dict | None) -> tuple[float, float, float]:
        """Compute per-run prompt/completion/reasoning costs from by_model usage."""
        if not llm_summary:
            return 0.0, 0.0, 0.0

        by_model = llm_summary.get("by_model", {})
        prompt_cost = 0.0
        completion_cost = 0.0
        reasoning_cost = 0.0

        for model_name, bucket in by_model.items():
            p_cost, c_cost, r_cost = _lookup_bucket_cost_by_type(model_name, bucket)
            prompt_cost += p_cost
            completion_cost += c_cost
            reasoning_cost += r_cost

        return prompt_cost, completion_cost, reasoning_cost

    # --- Totals ---
    totals_per_run_tokens: list[int] = []
    totals_per_run_costs: list[float] = []
    totals_calls = 0
    totals_prompt = 0
    totals_completion = 0
    totals_reasoning = 0
    totals_tokens = 0
    totals_cost = 0.0
    totals_prompt_cost = 0.0
    totals_completion_cost = 0.0
    totals_reasoning_cost = 0.0

    for j in jobs_with_usage:
        t = j.llm_usage_summary.get("totals", {})  # type: ignore[union-attr]
        totals_calls += t.get("calls", 0)
        totals_prompt += t.get("prompt_tokens", 0)
        totals_completion += t.get("completion_tokens", 0)
        totals_reasoning += t.get("reasoning_tokens", 0)
        totals_tokens += t.get("total_tokens", 0)

        run_prompt_cost, run_completion_cost, run_reasoning_cost = _extract_run_costs_by_type(
            j.llm_usage_summary,
        )
        run_total_cost = run_prompt_cost + run_completion_cost + run_reasoning_cost

        totals_cost += run_total_cost
        totals_prompt_cost += run_prompt_cost
        totals_completion_cost += run_completion_cost
        totals_reasoning_cost += run_reasoning_cost
        totals_per_run_tokens.append(t.get("total_tokens", 0))
        totals_per_run_costs.append(run_total_cost)

    totals_bucket = _build_aggregated_bucket(
        totals_per_run_tokens, totals_per_run_costs,
        totals_calls, totals_prompt, totals_completion,
        totals_reasoning, totals_tokens, totals_cost,
        totals_prompt_cost, totals_completion_cost, totals_reasoning_cost,
    )

    # --- Breakdown dimensions ---
    def _aggregate_dimension(
        dim_key: str,
        cost_mode: str = "none",
    ) -> dict[str, AggregatedUsageBucket]:
        # Accumulate per-key data across runs
        key_data: dict[str, dict] = defaultdict(lambda: {
            "calls": 0, "prompt": 0, "completion": 0, "reasoning": 0,
            "tokens": 0,
            "cost": 0.0,
            "prompt_cost": 0.0,
            "completion_cost": 0.0,
            "reasoning_cost": 0.0,
            "per_run_tokens": [],
            "per_run_costs": [],
        })

        for j in jobs_with_usage:
            dim = j.llm_usage_summary.get(dim_key, {})  # type: ignore[union-attr]
            for key, bucket in dim.items():
                d = key_data[key]
                prompt_tokens = max(0, int(bucket.get("prompt_tokens", 0) or 0))
                completion_tokens = max(0, int(bucket.get("completion_tokens", 0) or 0))
                reasoning_tokens = max(0, int(bucket.get("reasoning_tokens", 0) or 0))
                tok = max(0, int(bucket.get("total_tokens", 0) or 0))
                d["calls"] += bucket.get("calls", 0)
                d["prompt"] += prompt_tokens
                d["completion"] += completion_tokens
                d["reasoning"] += reasoning_tokens
                d["tokens"] += tok
                d["per_run_tokens"].append(tok)

                prompt_cost = 0.0
                completion_cost = 0.0
                reasoning_cost = 0.0
                if cost_mode == "model":
                    prompt_cost, completion_cost, reasoning_cost = _lookup_bucket_cost_by_type(
                        key,
                        bucket,
                    )
                elif cost_mode == "events_exact":
                    by_dim_cost_map: dict[str, dict[str, float]] = {}
                    if dim_key == "by_agent":
                        by_dim_cost_map = getattr(j, "llm_cost_by_agent", {})
                    elif dim_key == "by_component":
                        by_dim_cost_map = getattr(j, "llm_cost_by_component", {})
                    elif dim_key == "by_node":
                        by_dim_cost_map = getattr(j, "llm_cost_by_node", {})

                    cost_bucket = by_dim_cost_map.get(key, _empty_cost_bucket())
                    prompt_cost = float(cost_bucket.get("prompt_cost_usd", 0.0))
                    completion_cost = float(cost_bucket.get("completion_cost_usd", 0.0))
                    reasoning_cost = float(cost_bucket.get("reasoning_cost_usd", 0.0))

                total_cost = prompt_cost + completion_cost + reasoning_cost
                d["cost"] += total_cost
                d["prompt_cost"] += prompt_cost
                d["completion_cost"] += completion_cost
                d["reasoning_cost"] += reasoning_cost
                if cost_mode == "none":
                    d["per_run_costs"].append(0.0)
                else:
                    d["per_run_costs"].append(total_cost)

        result = {}
        for key, d in key_data.items():
            result[key] = _build_aggregated_bucket(
                d["per_run_tokens"], d["per_run_costs"],
                d["calls"], d["prompt"], d["completion"],
                d["reasoning"], d["tokens"], d["cost"],
                d["prompt_cost"], d["completion_cost"], d["reasoning_cost"],
            )
        return result

    return AggregatedUsageResponse(
        totals=totals_bucket,
        by_model=_aggregate_dimension("by_model", cost_mode="model"),
        by_agent=_aggregate_dimension("by_agent", cost_mode="events_exact"),
        by_node=_aggregate_dimension("by_node", cost_mode="events_exact"),
        by_component=_aggregate_dimension("by_component", cost_mode="events_exact"),
        runs_included=len(jobs_with_usage),
    )
