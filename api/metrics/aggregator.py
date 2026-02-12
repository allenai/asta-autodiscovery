"""GCS data aggregation and caching for the metrics dashboard.

Scans all users and jobs in GCS to build an in-memory cache of job snapshots.
Uses a stale-while-revalidate pattern with background refresh.
Incremental scanning skips terminal jobs that are already cached.
"""

from __future__ import annotations

import json
import logging
import statistics
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import UTC, datetime

from google.cloud import storage

from autodiscovery_jobs.config import JobConfig

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


# ---------------------------------------------------------------------------
# Job scanning
# ---------------------------------------------------------------------------

def _count_experiments_inline(
    bucket: storage.Bucket,
    userid: str,
    jobid: str,
) -> int:
    """Count completed experiment result files using match_glob on the shared bucket.

    Excludes the root node (mcts_node_1_0.json) which is the initialisation node,
    not a real experiment.
    """
    root_node = f"users/{userid}/jobs/{jobid}/output/mcts_node_1_0.json"
    try:
        blobs = bucket.list_blobs(
            match_glob=f"users/{userid}/jobs/{jobid}/output/mcts_node_*_*.json",
        )
        return sum(1 for b in blobs if b.name != root_node)
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
        n_requested = (metadata.get("n_experiments") or 0) if metadata else 0

        # Count completed experiments using shared bucket
        n_completed = _count_experiments_inline(bucket, userid, jobid)

        # Read LLM usage summary
        llm_summary = _read_gcs_json(bucket, f"{base_path}/output/llm_usage_summary.json")

        # Calculate LLM cost and infer model from usage data
        llm_cost = 0.0
        if llm_summary:
            llm_cost, _ = calculate_llm_cost(llm_summary)
        model = _infer_model(llm_summary)

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

    # Scan all remaining jobs in a single global thread pool
    scanned = 0
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
                    scanned += 1

    unique_users = len({k[0] for k in all_job_keys})
    elapsed = time.monotonic() - start_time
    logger.info(
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

        On cold start (no data), blocks until scan completes.
        If stale, serves existing data and refreshes in background.
        """
        with self._lock:
            if self._data is None:
                # Cold start: block until first scan
                self._do_refresh()
                return self._data  # type: ignore
            elif self._is_stale():
                self._trigger_background_refresh()
            return self._data

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
        try:
            self._do_refresh()
        finally:
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
    started_jobs = [j for j in jobs if j.status in STARTED_STATUSES]
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
    for j in jobs:
        if not j.created_at:
            continue
        date = j.created_at[:10]
        if date not in daily:
            daily[date] = DailyMetrics(date=date)
        day = daily[date]
        day.runs_started += 1
        if j.status == "SUCCEEDED":
            day.runs_succeeded += 1
        if j.status == "FAILED":
            day.runs_failed += 1
        day.llm_cost_usd += j.llm_cost_usd

    # Round daily costs
    for day in daily.values():
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

    # --- Totals ---
    totals_per_run_tokens: list[int] = []
    totals_per_run_costs: list[float] = []
    totals_calls = 0
    totals_prompt = 0
    totals_completion = 0
    totals_reasoning = 0
    totals_tokens = 0
    totals_cost = 0.0

    for j in jobs_with_usage:
        t = j.llm_usage_summary.get("totals", {})  # type: ignore[union-attr]
        totals_calls += t.get("calls", 0)
        totals_prompt += t.get("prompt_tokens", 0)
        totals_completion += t.get("completion_tokens", 0)
        totals_reasoning += t.get("reasoning_tokens", 0)
        totals_tokens += t.get("total_tokens", 0)
        totals_cost += j.llm_cost_usd
        totals_per_run_tokens.append(t.get("total_tokens", 0))
        totals_per_run_costs.append(j.llm_cost_usd)

    totals_bucket = _build_aggregated_bucket(
        totals_per_run_tokens, totals_per_run_costs,
        totals_calls, totals_prompt, totals_completion,
        totals_reasoning, totals_tokens, totals_cost,
    )

    # --- Breakdown dimensions ---
    def _aggregate_dimension(
        dim_key: str,
        include_cost: bool = False,
    ) -> dict[str, AggregatedUsageBucket]:
        # Accumulate per-key data across runs
        key_data: dict[str, dict] = defaultdict(lambda: {
            "calls": 0, "prompt": 0, "completion": 0, "reasoning": 0,
            "tokens": 0, "cost": 0.0, "per_run_tokens": [], "per_run_costs": [],
        })

        for j in jobs_with_usage:
            dim = j.llm_usage_summary.get(dim_key, {})  # type: ignore[union-attr]
            for key, bucket in dim.items():
                d = key_data[key]
                tok = bucket.get("total_tokens", 0)
                d["calls"] += bucket.get("calls", 0)
                d["prompt"] += bucket.get("prompt_tokens", 0)
                d["completion"] += bucket.get("completion_tokens", 0)
                d["reasoning"] += bucket.get("reasoning_tokens", 0)
                d["tokens"] += tok
                d["per_run_tokens"].append(tok)

                if include_cost:
                    # Per-model cost from pricing
                    pricing = _lookup_model_cost(key, bucket)
                    d["cost"] += pricing
                    d["per_run_costs"].append(pricing)
                else:
                    d["per_run_costs"].append(0.0)

        result = {}
        for key, d in key_data.items():
            result[key] = _build_aggregated_bucket(
                d["per_run_tokens"], d["per_run_costs"],
                d["calls"], d["prompt"], d["completion"],
                d["reasoning"], d["tokens"], d["cost"],
            )
        return result

    def _lookup_model_cost(model_name: str, bucket: dict) -> float:
        """Calculate cost for a single model bucket."""
        pricing = _lookup_pricing(model_name)
        prompt_tokens = bucket.get("prompt_tokens", 0)
        total_tokens = bucket.get("total_tokens", 0)
        output_tokens = max(0, total_tokens - prompt_tokens)
        return (prompt_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]

    return AggregatedUsageResponse(
        totals=totals_bucket,
        by_model=_aggregate_dimension("by_model", include_cost=True),
        by_agent=_aggregate_dimension("by_agent"),
        by_node=_aggregate_dimension("by_node"),
        by_component=_aggregate_dimension("by_component"),
        runs_included=len(jobs_with_usage),
    )
