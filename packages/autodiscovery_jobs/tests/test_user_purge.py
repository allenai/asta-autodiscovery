"""Tests for the maintainer-only per-user erasure helpers."""

import json
from unittest.mock import Mock

import pytest
from autodiscovery_jobs import gcs
from autodiscovery_jobs.exceptions import GCSError


def make_blob(name, size=100):
    """Build a mock blob that behaves like a listed GCS object."""
    blob = Mock()
    blob.name = name
    blob.size = size
    return blob


def wire_bucket(bucket, user_blobs=(), index_entries=None):
    """Route the mock bucket's list_blobs/blob calls to canned fixtures.

    Args:
        bucket: The mock bucket from the ``mock_storage_client`` fixture.
        user_blobs: Blobs to return under the ``users/`` prefix.
        index_entries: Mapping of jobid -> index entry payload.

    Returns:
        Dict of the mutable state the caller can assert against.
    """
    index_entries = index_entries or {}
    state = {"written": {}, "deleted": []}

    index_blobs = []
    for jobid, payload in index_entries.items():
        blob = make_blob(f"index/shared-runs/{jobid}", size=10)
        blob.download_as_text.return_value = json.dumps(payload)
        index_blobs.append(blob)

    def list_blobs(prefix=None, delimiter=None):
        if prefix == "index/shared-runs/":
            return iter(index_blobs)
        return iter([b for b in user_blobs if b.name.startswith(prefix or "")])

    def blob_factory(path):
        blob = Mock()
        blob.name = path
        blob.delete.side_effect = lambda: state["deleted"].append(path)
        blob.upload_from_string.side_effect = lambda data, **kw: state["written"].update(
            json.loads(data)
        )
        return blob

    bucket.list_blobs.side_effect = list_blobs
    bucket.blob.side_effect = blob_factory
    return state


@pytest.mark.parametrize("bad", ["", "   ", "users/other", "a/b"])
def test_validate_userid_rejects_prefix_widening(bad):
    with pytest.raises(ValueError):
        gcs._validate_userid(bad)


def test_summarize_user_data_counts_every_surface(mock_config, mock_storage_client):
    _, bucket = mock_storage_client
    sub = "google-oauth2|123"
    wire_bucket(
        bucket,
        user_blobs=[
            make_blob(f"users/{sub}/user.json", size=50),
            make_blob(f"users/{sub}/jobs/job1/metadata.json", size=200),
            make_blob(f"users/{sub}/jobs/job1/data/train.csv", size=1000),
            make_blob(f"users/{sub}/jobs/job2/output/mcts_node_1_0.json", size=300),
        ],
        index_entries={
            "job1": {"runid": "job1", "userid": sub},
            "job9": {"runid": "job9", "userid": "someone-else"},
        },
    )

    summary = gcs.summarize_user_data(sub, mock_config)

    assert summary.userid == sub
    assert summary.object_count == 4
    assert summary.total_bytes == 1550
    assert summary.job_ids == ["job1", "job2"]
    assert summary.has_user_profile is True
    assert summary.shared_run_ids == ["job1"]
    assert summary.active_job_ids == []
    assert not summary.is_empty


def test_summarize_user_data_reports_empty_subject(mock_config, mock_storage_client):
    _, bucket = mock_storage_client
    wire_bucket(bucket)

    summary = gcs.summarize_user_data("unknown-sub", mock_config)

    assert summary.object_count == 0
    assert summary.job_ids == []
    assert summary.is_empty


def test_summarize_user_data_flags_active_jobs(mock_config, mock_storage_client, monkeypatch):
    _, bucket = mock_storage_client
    sub = "google-oauth2|123"
    wire_bucket(
        bucket,
        user_blobs=[
            make_blob(f"users/{sub}/jobs/running-job/run_details.json"),
            make_blob(f"users/{sub}/jobs/done-job/run_details.json"),
        ],
    )

    def fake_run_details(userid, jobid, config=None):
        details = Mock()
        details.status = "RUNNING" if jobid == "running-job" else "SUCCEEDED"
        return details

    monkeypatch.setattr("autodiscovery_jobs.run_details.get_run_details", fake_run_details)

    summary = gcs.summarize_user_data(sub, mock_config)

    assert summary.job_ids == ["done-job", "running-job"]
    assert summary.active_job_ids == ["running-job"]


def test_purge_user_data_deletes_all_surfaces(mock_config, mock_storage_client):
    _, bucket = mock_storage_client
    sub = "google-oauth2|123"
    state = wire_bucket(
        bucket,
        user_blobs=[
            make_blob(f"users/{sub}/user.json", size=50),
            make_blob(f"users/{sub}/jobs/job1/data/train.csv", size=1000),
        ],
        index_entries={"job1": {"runid": "job1", "userid": sub}},
    )

    result = gcs.purge_user_data(sub, mock_config)

    assert result["deleted_objects"] == [
        f"users/{sub}/jobs/job1/data/train.csv",
        f"users/{sub}/user.json",
    ]
    assert result["deleted_bytes"] == 1050
    assert result["deleted_shared_run_ids"] == ["job1"]
    # The blobs themselves were deleted, and the index entry was removed by path.
    assert "index/shared-runs/job1" in state["deleted"]
    # Nothing outside the subject's own data was rewritten.
    assert state["written"] == {}


def test_purge_user_data_dry_run_deletes_nothing(mock_config, mock_storage_client):
    _, bucket = mock_storage_client
    sub = "google-oauth2|123"
    user_blobs = [make_blob(f"users/{sub}/jobs/job1/data/train.csv", size=1000)]
    state = wire_bucket(
        bucket,
        user_blobs=user_blobs,
        index_entries={"job1": {"runid": "job1", "userid": sub}},
    )

    result = gcs.purge_user_data(sub, mock_config, dry_run=True)

    assert result["dry_run"] is True
    assert result["deleted_objects"] == [f"users/{sub}/jobs/job1/data/train.csv"]
    assert result["deleted_shared_run_ids"] == ["job1"]
    user_blobs[0].delete.assert_not_called()
    assert state["deleted"] == []
    assert state["written"] == {}


def test_purge_user_data_rejects_bad_userid(mock_config, mock_storage_client):
    with pytest.raises(ValueError):
        gcs.purge_user_data("has/slash", mock_config)


def test_purge_user_data_wraps_gcs_failures(mock_config, mock_storage_client):
    _, bucket = mock_storage_client
    bucket.list_blobs.side_effect = Exception("boom")

    with pytest.raises(GCSError):
        gcs.purge_user_data("google-oauth2|123", mock_config)
