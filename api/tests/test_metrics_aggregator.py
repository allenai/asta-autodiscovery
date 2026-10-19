"""Tests for the metrics cache's configuration loading and failure handling."""

import json
import re
from unittest.mock import patch

import pytest
from metrics import aggregator
from metrics.aggregator import AggregatedData, JobSnapshot, MetricsCache

BUCKET_ENV_VARS = ("GCS_BUCKET", "AUTODISCOVERY_BUCKET", "GCP_PROJECT")


@pytest.fixture(autouse=True)
def clear_bucket_env(monkeypatch):
    """Isolate tests from the ambient deployment configuration."""
    for name in BUCKET_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_cache_reads_bucket_from_environment(monkeypatch):
    """The cache must scan the deployment's bucket, not the built-in default."""
    monkeypatch.setenv("GCS_BUCKET", "bucket-from-deployment")

    cache = MetricsCache()

    assert cache._config.bucket == "bucket-from-deployment"


def test_cache_accepts_legacy_bucket_env_alias(monkeypatch):
    monkeypatch.setenv("AUTODISCOVERY_BUCKET", "bucket-from-alias")

    cache = MetricsCache()

    assert cache._config.bucket == "bucket-from-alias"


def test_scan_all_jobs_propagates_discovery_failure(tmp_path):
    """A failed listing must raise, not masquerade as an empty dataset."""
    config = aggregator.JobConfig(storage_backend="local", storage_dir=str(tmp_path))

    with (
        patch.object(
            aggregator, "_discover_jobs", side_effect=RuntimeError("404 store unreadable")
        ),
        # The message names the store that failed, whichever backend it is.
        pytest.raises(RuntimeError, match=re.escape(tmp_path.as_uri())),
    ):
        aggregator._scan_all_jobs(config)


def _snapshot() -> JobSnapshot:
    return JobSnapshot(userid="u1", jobid="j1", status="SUCCEEDED")


def test_failed_refresh_preserves_previous_data_and_records_error():
    cache = MetricsCache()
    previous = AggregatedData(jobs=[_snapshot()], refreshed_at="2026-01-01T00:00:00+00:00")
    cache._data = previous

    with patch.object(aggregator, "_scan_all_jobs", side_effect=RuntimeError("boom")):
        cache._do_refresh()

    assert cache._data is previous
    assert cache.last_error == "refresh_failed"


def test_cold_start_returns_empty_data_while_background_refresh_runs():
    cache = MetricsCache()

    with (
        patch.object(aggregator, "get_store", side_effect=RuntimeError("no cache")),
        patch.object(aggregator.threading, "Thread"),
    ):
        data = cache.get_data()

    assert isinstance(data, AggregatedData)
    assert data.jobs == []
    assert data.refreshed_at is None


def test_automatic_refresh_respects_backoff_after_attempt():
    cache = MetricsCache(refresh_interval_seconds=300)

    with (
        patch.object(aggregator.time, "monotonic", side_effect=[100.0, 101.0]),
        patch.object(aggregator.threading, "Thread") as thread,
    ):
        cache._trigger_background_refresh()
        cache._refreshing = False  # Simulate the background attempt completing.
        cache._trigger_background_refresh()

    thread.assert_called_once()
    thread.return_value.start.assert_called_once()
    assert cache._last_refresh_attempt_monotonic == 100.0


def test_forced_refresh_bypasses_attempt_backoff():
    cache = MetricsCache(refresh_interval_seconds=300)
    cache._last_refresh_attempt_monotonic = 100.0

    with (
        patch.object(aggregator.time, "monotonic", return_value=101.0),
        patch.object(aggregator.threading, "Thread") as thread,
    ):
        cache.force_refresh()

    thread.assert_called_once()
    thread.return_value.start.assert_called_once()


def test_failed_thread_start_clears_refreshing_state():
    cache = MetricsCache()

    with patch.object(aggregator.threading, "Thread") as thread:
        thread.return_value.start.side_effect = RuntimeError("cannot start thread")
        with pytest.raises(RuntimeError, match="cannot start thread"):
            cache.force_refresh()

    assert cache.is_refreshing is False


def test_successful_refresh_clears_recorded_error():
    cache = MetricsCache()
    cache._last_error = "boom"
    fresh = AggregatedData(jobs=[_snapshot()], refreshed_at="2026-01-02T00:00:00+00:00")

    with (
        patch.object(aggregator, "_scan_all_jobs", return_value=fresh),
        # Persisting the snapshot fails; a successful scan must still clear the error.
        patch.object(aggregator, "get_store", side_effect=RuntimeError("no credentials")),
    ):
        cache._do_refresh()

    assert cache._data is fresh
    assert cache.last_error is None


@pytest.mark.parametrize(("created_at", "expected"), [("2026-12-31", 4.5), ("2027-01-01", 9.0)])
def test_gemini_pricing_date_reaches_all_dashboard_views(tmp_path, created_at, expected):
    """Rescanning old runs must not reprice them using the dashboard's current date."""
    config = aggregator.JobConfig(storage_backend="local", storage_dir=str(tmp_path))
    store = aggregator.get_store(config)
    base = "users/u1/jobs/j1"
    model = "vertex_ai/gemini-3.8-flash"
    bucket = {
        "calls": 1,
        "prompt_tokens": 1_000_000,
        "completion_tokens": 800_000,
        "reasoning_tokens": 200_000,
        "total_tokens": 2_000_000,
    }
    summary = {
        "totals": bucket,
        "by_model": {model: bucket},
        "by_agent": {"programmer": bucket},
        "by_component": {"chat": bucket},
        "by_node": {"1": bucket},
    }
    store.write_text(
        f"{base}/run_details.json", json.dumps({"status": "SUCCEEDED", "created_at": created_at})
    )
    store.write_text(f"{base}/output/llm_usage_summary.json", json.dumps(summary))
    store.write_text(
        f"{base}/output/llm_usage_events.jsonl",
        json.dumps(
            {
                "model": model,
                "agent_name": "programmer",
                "component": "chat",
                "node_id": "1",
                "usage": bucket,
            }
        ),
    )

    job = aggregator._scan_job("u1", "j1", store)
    assert job is not None
    assert job.llm_cost_usd == expected
    cache = MetricsCache()
    cache._data = AggregatedData(jobs=[job], refreshed_at="2099-01-01T00:00:00Z")
    with patch.object(aggregator, "get_metrics_cache", return_value=cache):
        detail = aggregator.compute_run_metrics("u1", "j1")
        assert detail["llm_cost_by_model"] == {model: expected}
        assert detail["llm_cost_usd"] == expected
        usage = aggregator.compute_aggregated_usage()

    assert usage.totals.total_cost_usd == expected
    for breakdown in (usage.by_model, usage.by_agent, usage.by_component, usage.by_node):
        cost = next(iter(breakdown.values()))
        assert cost.total_cost_usd == expected
        assert cost.total_prompt_cost_usd == pytest.approx(expected / 6)
        assert cost.total_completion_cost_usd == pytest.approx(expected * 2 / 3)
        assert cost.total_reasoning_cost_usd == pytest.approx(expected / 6)


def test_persisted_costs_from_before_dated_pricing_are_rebuilt(tmp_path):
    config = aggregator.JobConfig(storage_backend="local", storage_dir=str(tmp_path))
    store = aggregator.get_store(config)
    store.write_text(
        aggregator.PERSIST_BLOB_PATH,
        json.dumps({"schema_version": 1, "jobs": [{"llm_cost_usd": 4.5}]}),
    )

    assert aggregator._load_persisted_cache(store) is None
