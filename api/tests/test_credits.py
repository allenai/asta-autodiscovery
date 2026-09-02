"""Tests for credit aggregation caching."""

from unittest.mock import patch

from autodiscovery_jobs import JobConfig
from utils import credits


def setup_function():
    credits._credits_cache.clear()
    credits._credits_refresh_locks.clear()


def test_cached_user_credits_reuses_result_for_same_user():
    config = JobConfig(bucket="bucket", project_id="project")
    expected = credits.UserCredits(granted=500, consumed=10, pending=5, available=485)

    with patch.object(credits, "get_user_credits", return_value=expected) as calculate:
        assert credits.get_cached_user_credits("user", config) == expected
        assert credits.get_cached_user_credits("user", config) == expected

    calculate.assert_called_once_with(userid="user", config=config)


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
