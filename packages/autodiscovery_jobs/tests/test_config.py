"""Tests for JobConfig construction, overrides, and hashability."""

import pytest
from autodiscovery_jobs.config import JobConfig


def test_config_is_hashable_and_value_equal():
    """Frozen dataclass: equal-valued instances hash alike, so they share a cache key."""
    first = JobConfig(bucket="bucket", project_id="project")
    second = JobConfig(bucket="bucket", project_id="project")

    assert first == second
    assert hash(first) == hash(second)
    assert len({first, second}) == 1
    assert {first: "value"}[second] == "value"


def test_config_is_immutable():
    config = JobConfig(bucket="bucket")

    with pytest.raises(AttributeError):
        config.bucket = "other"  # type: ignore[misc]


def test_from_env_applies_known_overrides_and_ignores_unknown(monkeypatch):
    for var in ("GCS_BUCKET", "AUTODISCOVERY_BUCKET", "GCP_PROJECT", "GCP_REGION"):
        monkeypatch.delenv(var, raising=False)

    config = JobConfig.from_env(bucket="custom-bucket", not_a_field="ignored")

    assert config.bucket == "custom-bucket"
    assert config.region == JobConfig.region
    assert not hasattr(config, "not_a_field")
