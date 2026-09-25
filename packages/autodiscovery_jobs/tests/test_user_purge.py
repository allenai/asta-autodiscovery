"""Tests for the maintainer-only per-user erasure helpers.

These run against the default filesystem store on a real temp directory rather
than a mocked GCS client: erasure is defined by what is left in the store
afterwards, which a wire-level mock cannot show. The purge is backend-agnostic,
so covering it on the store the ``local`` backend uses also covers the GCS one.
"""

import json

import pytest
from autodiscovery_jobs import persistence
from autodiscovery_jobs.exceptions import StorageError
from autodiscovery_jobs.storage import get_store


def seed(config, objects=None, index_entries=None):
    """Write canned objects and shared-run index entries into the store.

    Args:
        config: Config selecting the store to seed.
        objects: Mapping of object key -> byte length to write.
        index_entries: Mapping of jobid -> index entry payload.

    Returns:
        The store, so callers can assert against it directly.
    """
    store = get_store(config)
    for key, size in (objects or {}).items():
        store.write_bytes(key, b"x" * size)
    for jobid, payload in (index_entries or {}).items():
        store.write_text(f"index/shared-runs/{jobid}", json.dumps(payload))
    return store


@pytest.mark.parametrize("bad", ["", "   ", "users/other", "a/b"])
def test_validate_userid_rejects_prefix_widening(bad):
    with pytest.raises(ValueError):
        persistence._validate_userid(bad)


def test_summarize_user_data_counts_every_surface(local_config):
    sub = "google-oauth2|123"
    seed(
        local_config,
        objects={
            f"users/{sub}/user.json": 50,
            f"users/{sub}/jobs/job1/metadata.json": 200,
            f"users/{sub}/jobs/job1/data/train.csv": 1000,
            f"users/{sub}/jobs/job2/output/mcts_node_1_0.json": 300,
        },
        index_entries={
            "job1": {"runid": "job1", "userid": sub},
            "job9": {"runid": "job9", "userid": "someone-else"},
        },
    )

    summary = persistence.summarize_user_data(sub, local_config)

    assert summary.userid == sub
    assert summary.object_count == 4
    assert summary.total_bytes == 1550
    assert summary.job_ids == ["job1", "job2"]
    assert summary.has_user_profile is True
    # Only the subject's own index entry is in scope; job9 belongs to someone else.
    assert summary.shared_run_ids == ["job1"]
    assert summary.active_job_ids == []
    assert not summary.is_empty


def test_summarize_user_data_reports_empty_subject(local_config):
    seed(local_config)

    summary = persistence.summarize_user_data("unknown-sub", local_config)

    assert summary.object_count == 0
    assert summary.job_ids == []
    assert summary.is_empty


def test_summarize_user_data_flags_active_jobs(local_config):
    sub = "google-oauth2|123"
    store = get_store(local_config)
    for jobid, status in [("running-job", "RUNNING"), ("done-job", "SUCCEEDED")]:
        store.write_text(
            f"users/{sub}/jobs/{jobid}/run_details.json",
            json.dumps({"status": status}),
        )

    summary = persistence.summarize_user_data(sub, local_config)

    assert summary.job_ids == ["done-job", "running-job"]
    # A job that can still write must be cancelled before a purge is final.
    assert summary.active_job_ids == ["running-job"]


def test_purge_user_data_deletes_all_surfaces(local_config):
    sub = "google-oauth2|123"
    store = seed(
        local_config,
        objects={
            f"users/{sub}/user.json": 50,
            f"users/{sub}/jobs/job1/data/train.csv": 1000,
            # A second subject, to prove the purge stays scoped.
            "users/other-sub/user.json": 25,
        },
        index_entries={
            "job1": {"runid": "job1", "userid": sub},
            "job9": {"runid": "job9", "userid": "other-sub"},
        },
    )

    result = persistence.purge_user_data(sub, local_config)

    assert result["deleted_objects"] == [
        f"users/{sub}/jobs/job1/data/train.csv",
        f"users/{sub}/user.json",
    ]
    assert result["deleted_bytes"] == 1050
    assert result["deleted_shared_run_ids"] == ["job1"]

    # The subject is gone from the store, index entry included.
    assert list(store.list(f"users/{sub}/")) == []
    assert not store.exists("index/shared-runs/job1")
    # The other subject is untouched.
    assert store.exists("users/other-sub/user.json")
    assert store.exists("index/shared-runs/job9")


def test_purge_user_data_dry_run_deletes_nothing(local_config):
    sub = "google-oauth2|123"
    store = seed(
        local_config,
        objects={f"users/{sub}/jobs/job1/data/train.csv": 1000},
        index_entries={"job1": {"runid": "job1", "userid": sub}},
    )

    result = persistence.purge_user_data(sub, local_config, dry_run=True)

    assert result["dry_run"] is True
    assert result["deleted_objects"] == [f"users/{sub}/jobs/job1/data/train.csv"]
    assert result["deleted_shared_run_ids"] == ["job1"]
    # Reported, but still present.
    assert store.exists(f"users/{sub}/jobs/job1/data/train.csv")
    assert store.exists("index/shared-runs/job1")


def test_purge_user_data_rejects_bad_userid(local_config):
    with pytest.raises(ValueError):
        persistence.purge_user_data("has/slash", local_config)


def test_purge_user_data_wraps_store_failures(local_config, monkeypatch):
    def boom(*args, **kwargs):
        raise OSError("boom")

    monkeypatch.setattr("autodiscovery_jobs.storage.local.FilesystemStore.list", boom)

    with pytest.raises(StorageError):
        persistence.purge_user_data("google-oauth2|123", local_config)
