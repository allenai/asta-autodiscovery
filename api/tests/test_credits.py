"""Tests for credit aggregation caching."""

from unittest.mock import patch

from autodiscovery_jobs import JobConfig
from utils import credits


def setup_function():
    credits._aggregate_user_credits.cache_clear()


def test_cached_user_credits_reuses_result_for_same_user():
    config = JobConfig(bucket="bucket", project_id="project")
    expected = credits.UserCredits(granted=500, consumed=10, pending=5, available=485)

    with patch.object(credits, "get_user_credits", return_value=expected) as calculate:
        assert credits.get_cached_user_credits("user", config) == expected
        assert credits.get_cached_user_credits("user", config) == expected

    calculate.assert_called_once_with(userid="user", config=config)


def test_cached_user_credits_reuses_result_for_equal_configs():
    """Distinct but equal JobConfigs share one cache key, since JobConfig is frozen."""
    expected = credits.UserCredits(granted=500, consumed=10, pending=5, available=485)

    with patch.object(credits, "get_user_credits", return_value=expected) as calculate:
        assert credits.get_cached_user_credits("user", JobConfig(bucket="bucket")) == expected
        assert credits.get_cached_user_credits("user", JobConfig(bucket="bucket")) == expected

    assert calculate.call_count == 1


def test_cached_user_credits_is_scoped_by_config():
    with patch.object(credits, "get_user_credits") as calculate:
        calculate.side_effect = [
            credits.UserCredits(500, 1, 0, 499),
            credits.UserCredits(500, 2, 0, 498),
        ]
        assert credits.get_cached_user_credits("user", JobConfig(bucket="first")).consumed == 1
        assert credits.get_cached_user_credits("user", JobConfig(bucket="second")).consumed == 2

    assert calculate.call_count == 2


def test_cached_user_credits_is_scoped_by_user():
    config = JobConfig(bucket="bucket", project_id="project")

    with patch.object(credits, "get_user_credits") as calculate:
        calculate.side_effect = [
            credits.UserCredits(500, 1, 0, 499),
            credits.UserCredits(500, 2, 0, 498),
        ]
        assert credits.get_cached_user_credits("first", config).consumed == 1
        assert credits.get_cached_user_credits("second", config).consumed == 2

    assert calculate.call_count == 2


def test_cached_user_credits_expires_after_ttl():
    config = JobConfig(bucket="bucket", project_id="project")

    with (
        patch.object(credits, "get_user_credits") as calculate,
        patch.object(credits, "monotonic") as clock,
    ):
        calculate.side_effect = [
            credits.UserCredits(500, 1, 0, 499),
            credits.UserCredits(500, 2, 0, 498),
        ]
        clock.return_value = 0.0
        assert credits.get_cached_user_credits("user", config).consumed == 1
        clock.return_value = credits.CREDITS_CACHE_TTL_SECONDS / 2
        assert credits.get_cached_user_credits("user", config).consumed == 1
        clock.return_value = credits.CREDITS_CACHE_TTL_SECONDS
        assert credits.get_cached_user_credits("user", config).consumed == 2

    assert calculate.call_count == 2
