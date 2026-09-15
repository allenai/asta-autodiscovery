"""Tests for the one-time credit grant script.

The script lives in ``api/scripts``, which is not importable as a package (the
repository root has its own ``scripts/`` that shadows it), so it is loaded by
path.
"""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from autodiscovery_jobs import JobConfig
from autodiscovery_jobs.user_profile import UserProfile

_SCRIPT = Path(__file__).parents[1] / "scripts" / "grant_credits.py"
_spec = importlib.util.spec_from_file_location("grant_credits", _SCRIPT)
grant_credits = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(grant_credits)

CONFIG = JobConfig(bucket="bucket", project_id="project")
CUTOFF = datetime(2026, 9, 15, 23, 0, 0, tzinfo=UTC)
BEFORE = datetime(2026, 5, 1, tzinfo=UTC)
AFTER = datetime(2026, 9, 20, tzinfo=UTC)


def _profile(granted=None, created_at=""):
    return UserProfile(granted_credits=granted, created_at=created_at, updated_at="")


# --- resolve_base_credits ------------------------------------------------


def test_user_with_override_is_credited_from_that_override():
    with patch.object(grant_credits, "get_user_profile", return_value=_profile(2500)):
        base, _ = grant_credits.resolve_base_credits("u", CUTOFF, CONFIG)
    assert base == 2500


def test_profileless_user_is_credited_from_the_pinned_old_default():
    """Not from DEFAULT_CREDITS_GRANTED, which has already been raised."""
    with (
        patch.object(grant_credits, "get_user_profile", return_value=None),
        patch.object(grant_credits, "get_first_seen", return_value=BEFORE),
    ):
        base, _ = grant_credits.resolve_base_credits("u", CUTOFF, CONFIG)
    assert base == grant_credits.OLD_DEFAULT_CREDITS == 500


def test_user_first_seen_after_cutoff_is_skipped_as_a_new_signup():
    with (
        patch.object(grant_credits, "get_user_profile", return_value=None),
        patch.object(grant_credits, "get_first_seen", return_value=AFTER),
    ):
        base, reason = grant_credits.resolve_base_credits("u", CUTOFF, CONFIG)
    assert base is None
    assert "new user" in reason


def test_undatable_user_is_skipped_rather_than_guessed():
    with (
        patch.object(grant_credits, "get_user_profile", return_value=None),
        patch.object(grant_credits, "get_first_seen", return_value=None),
    ):
        base, _ = grant_credits.resolve_base_credits("u", CUTOFF, CONFIG)
    assert base is None


def test_profile_timestamp_is_preferred_over_listing_objects():
    profile = _profile(granted=None, created_at=BEFORE.isoformat())
    with (
        patch.object(grant_credits, "get_user_profile", return_value=profile),
        patch.object(grant_credits, "get_first_seen") as listed,
    ):
        base, _ = grant_credits.resolve_base_credits("u", CUTOFF, CONFIG)
    assert base == 500
    listed.assert_not_called()


# --- grant_user ----------------------------------------------------------


@pytest.fixture
def granting():
    """Patch a fresh user with a 500 override and capture the writes."""
    with (
        patch.object(grant_credits, "get_user_profile", return_value=_profile(500)),
        patch.object(grant_credits, "read_marker", return_value=None),
        patch.object(grant_credits, "write_marker") as write_marker,
        patch.object(grant_credits, "update_user_profile") as update_profile,
    ):
        yield write_marker, update_profile


def test_grant_adds_the_full_amount(granting):
    _, update_profile = granting
    assert grant_credits.grant_user("u", CUTOFF, CONFIG, dry_run=False) == "granted"
    update_profile.assert_called_once_with("u", {"granted_credits": 1500}, CONFIG)


def test_marker_is_written_before_the_profile(granting):
    """A crash between the two must leave the grant detectable, not repeatable.

    Marker-then-profile leaves a marker whose "before" still matches the
    profile, which the next run retries. The reverse order would leave a
    granted user with no marker -- indistinguishable from an ungranted one.
    """
    write_marker, update_profile = granting
    order = []
    write_marker.side_effect = lambda *a, **k: order.append("marker")
    update_profile.side_effect = lambda *a, **k: order.append("profile")

    grant_credits.grant_user("u", CUTOFF, CONFIG, dry_run=False)

    assert order == ["marker", "profile"]


def test_dry_run_writes_nothing(granting):
    write_marker, update_profile = granting
    assert grant_credits.grant_user("u", CUTOFF, CONFIG, dry_run=True) == "granted"
    write_marker.assert_not_called()
    update_profile.assert_not_called()


def test_rerun_skips_a_user_already_granted():
    """The whole point of the marker: +1000 compounds if repeated."""
    marker = {"previous_granted": 500, "new_granted": 1500}
    with (
        patch.object(grant_credits, "get_user_profile", return_value=_profile(1500)),
        patch.object(grant_credits, "read_marker", return_value=marker),
        patch.object(grant_credits, "update_user_profile") as update_profile,
    ):
        assert grant_credits.grant_user("u", CUTOFF, CONFIG, dry_run=False) == "skipped"
    update_profile.assert_not_called()


def test_interrupted_grant_is_retried_to_the_recorded_value():
    """Marker written, profile write lost: reapply, and do not stack a second grant."""
    marker = {"previous_granted": 500, "new_granted": 1500}
    with (
        patch.object(grant_credits, "get_user_profile", return_value=_profile(500)),
        patch.object(grant_credits, "read_marker", return_value=marker),
        patch.object(grant_credits, "write_marker"),
        patch.object(grant_credits, "update_user_profile") as update_profile,
    ):
        assert grant_credits.grant_user("u", CUTOFF, CONFIG, dry_run=False) == "granted"
    update_profile.assert_called_once_with("u", {"granted_credits": 1500}, CONFIG)


def test_profile_changed_since_the_grant_is_left_alone():
    marker = {"previous_granted": 500, "new_granted": 1500}
    with (
        patch.object(grant_credits, "get_user_profile", return_value=_profile(9000)),
        patch.object(grant_credits, "read_marker", return_value=marker),
        patch.object(grant_credits, "update_user_profile") as update_profile,
    ):
        outcome = grant_credits.grant_user("u", CUTOFF, CONFIG, dry_run=False)
    assert outcome == "needs_review"
    update_profile.assert_not_called()
