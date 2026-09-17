"""Tests for the one-time credit grant script.

Loaded by path: the repository root has its own ``scripts/``, which shadows
``api/scripts`` and stops it importing as a package.
"""

import importlib.util
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import PreconditionFailed

_SCRIPT = Path(__file__).parents[1] / "scripts" / "grant_credits.py"
_spec = importlib.util.spec_from_file_location("grant_credits", _SCRIPT)
grant_credits = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(grant_credits)

GENERATION = 1234


def make_bucket(document, generation=GENERATION):
    """A bucket whose profile blob returns ``document``; None means no profile."""
    bucket = MagicMock()
    if document is None:
        bucket.get_blob.return_value = None
    else:
        blob = MagicMock()
        blob.generation = generation
        blob.download_as_text.return_value = json.dumps(document)
        bucket.get_blob.return_value = blob
    return bucket


def written_document(bucket):
    upload = bucket.blob.return_value.upload_from_string
    return json.loads(upload.call_args.args[0])


def profile(granted=500, grants=None):
    return {
        "granted_credits": granted,
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "grants": grants or [],
    }


# --- eligibility ---------------------------------------------------------


def test_user_without_a_profile_is_skipped():
    bucket = make_bucket(None)
    assert grant_credits.grant_user(bucket, "u", dry_run=False) == "skipped"
    bucket.blob.return_value.upload_from_string.assert_not_called()


def test_user_whose_override_is_null_is_skipped():
    bucket = make_bucket(profile(granted=None))
    assert grant_credits.grant_user(bucket, "u", dry_run=False) == "skipped"
    bucket.blob.return_value.upload_from_string.assert_not_called()


# --- the grant itself ----------------------------------------------------


def test_grant_adds_the_credits_and_records_the_grant():
    bucket = make_bucket(profile(granted=500))
    assert grant_credits.grant_user(bucket, "u", dry_run=False) == "granted"

    document = written_document(bucket)
    assert document["granted_credits"] == 1500
    assert [entry["id"] for entry in document["grants"]] == [grant_credits.GRANT_ID]
    assert document["grants"][0]["amount"] == 1000
    assert document["grants"][0]["previous_granted"] == 500


def test_grant_preserves_unrelated_profile_fields():
    bucket = make_bucket(profile(granted=500) | {"something_else": "keep me"})
    grant_credits.grant_user(bucket, "u", dry_run=False)
    assert written_document(bucket)["something_else"] == "keep me"


def test_grant_appends_to_an_existing_grants_list():
    earlier = {"id": "some-earlier-grant", "amount": 250}
    bucket = make_bucket(profile(granted=750, grants=[earlier]))
    grant_credits.grant_user(bucket, "u", dry_run=False)

    document = written_document(bucket)
    assert document["grants"][0] == earlier
    assert document["grants"][1]["id"] == grant_credits.GRANT_ID
    assert document["granted_credits"] == 1750


def test_write_is_conditional_on_the_generation_that_was_read():
    bucket = make_bucket(profile(granted=500), generation=99)
    grant_credits.grant_user(bucket, "u", dry_run=False)
    upload = bucket.blob.return_value.upload_from_string
    assert upload.call_args.kwargs["if_generation_match"] == 99


def test_dry_run_writes_nothing():
    bucket = make_bucket(profile(granted=500))
    assert grant_credits.grant_user(bucket, "u", dry_run=True) == "granted"
    bucket.blob.return_value.upload_from_string.assert_not_called()


# --- re-running ----------------------------------------------------------


def test_rerun_skips_a_user_already_carrying_this_grant():
    # The point of recording the grant: the amount compounds if repeated.
    applied = [{"id": grant_credits.GRANT_ID, "amount": 1000}]
    bucket = make_bucket(profile(granted=1500, grants=applied))
    assert grant_credits.grant_user(bucket, "u", dry_run=False) == "skipped"
    bucket.blob.return_value.upload_from_string.assert_not_called()


def test_an_unrelated_credit_change_does_not_block_the_grant():
    # State is tracked by grant id, not by comparing balances.
    bucket = make_bucket(profile(granted=9000))
    assert grant_credits.grant_user(bucket, "u", dry_run=False) == "granted"
    assert written_document(bucket)["granted_credits"] == 10000


# --- concurrency ---------------------------------------------------------


def test_a_profile_changed_before_the_write_is_reported_not_clobbered():
    bucket = make_bucket(profile(granted=500))
    bucket.blob.return_value.upload_from_string.side_effect = PreconditionFailed("412")
    assert grant_credits.grant_user(bucket, "u", dry_run=False) == "conflict"


def test_a_profile_changed_during_the_read_is_reported():
    bucket = make_bucket(profile(granted=500))
    bucket.get_blob.return_value.download_as_text.side_effect = PreconditionFailed("412")
    assert grant_credits.grant_user(bucket, "u", dry_run=False) == "conflict"


def test_a_profile_with_no_generation_cannot_be_written_safely():
    bucket = make_bucket(profile(granted=500), generation=None)
    with pytest.raises(ValueError):
        grant_credits.read_profile(bucket, "u")
