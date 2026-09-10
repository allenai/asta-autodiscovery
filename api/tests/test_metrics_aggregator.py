"""Tests for the metrics cache's configuration loading and failure handling."""

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


def test_scan_all_jobs_propagates_discovery_failure():
    """A failed bucket listing must raise, not masquerade as an empty dataset."""
    config = aggregator.JobConfig(bucket="unreadable-bucket")

    discovery_failed = patch.object(
        aggregator, "_discover_jobs_via_glob", side_effect=RuntimeError("404 bucket missing")
    )

    with (
        patch.object(aggregator.storage, "Client"),
        discovery_failed,
        pytest.raises(RuntimeError, match="unreadable-bucket"),
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


def test_successful_refresh_clears_recorded_error():
    cache = MetricsCache()
    cache._last_error = "boom"
    fresh = AggregatedData(jobs=[_snapshot()], refreshed_at="2026-01-02T00:00:00+00:00")

    with (
        patch.object(aggregator, "_scan_all_jobs", return_value=fresh),
        patch.object(aggregator.storage, "Client", side_effect=RuntimeError("no credentials")),
    ):
        cache._do_refresh()

    assert cache._data is fresh
    assert cache.last_error is None
