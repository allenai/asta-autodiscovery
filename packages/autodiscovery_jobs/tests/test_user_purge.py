"""Tests for the maintainer-only per-user erasure helpers."""

import json
from unittest.mock import Mock

import pytest
from autodiscovery_jobs import asta_gcs, gcs
from autodiscovery_jobs.exceptions import GCSError


def make_blob(name, size=100):
    """Build a mock blob that behaves like a listed GCS object."""
    blob = Mock()
    blob.name = name
    blob.size = size
    return blob


def wire_bucket(bucket, user_blobs=(), index_entries=None, metrics_jobs=None):
    """Route the mock bucket's list_blobs/blob calls to canned fixtures.

    Args:
        bucket: The mock bucket from the ``mock_storage_client`` fixture.
        user_blobs: Blobs to return under the ``users/`` prefix.
        index_entries: Mapping of jobid -> index entry payload.
        metrics_jobs: Rows for the persisted metrics cache, or None for no cache.

    Returns:
        Dict of the mutable state the caller can assert against.
    """
    index_entries = index_entries or {}
    state = {"metrics_jobs": metrics_jobs, "written": {}, "deleted": []}

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
        if path == gcs.METRICS_CACHE_BLOB_PATH:
            if state["metrics_jobs"] is None:
                blob.download_as_text.side_effect = Exception("404")
            else:
                blob.download_as_text.return_value = json.dumps(
                    {"schema_version": 1, "jobs": state["metrics_jobs"]}
                )
            blob.upload_from_string.side_effect = lambda data, **kw: state["written"].update(
                json.loads(data)
            )
        else:
            blob.delete.side_effect = lambda: state["deleted"].append(path)
        return blob

    bucket.list_blobs.side_effect = list_blobs
    bucket.blob.side_effect = blob_factory
    return state


@pytest.mark.parametrize("bad", ["", "   ", "users/other", "a/b"])
def test_validate_userid_rejects_prefix_widening(bad):
    with pytest.raises(ValueError):
        gcs._validate_userid(bad)


@pytest.mark.parametrize("bad", ["", "   ", "uuid/../other"])
def test_validate_user_uuid_rejects_prefix_widening(bad):
    with pytest.raises(ValueError):
        asta_gcs._validate_user_uuid(bad)


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
        metrics_jobs=[{"userid": sub, "jobid": "job1"}, {"userid": "other", "jobid": "job9"}],
    )

    summary = gcs.summarize_user_data(sub, mock_config)

    assert summary.userid == sub
    assert summary.object_count == 4
    assert summary.total_bytes == 1550
    assert summary.job_ids == ["job1", "job2"]
    assert summary.has_user_profile is True
    assert summary.shared_run_ids == ["job1"]
    assert summary.metrics_cache_entries == 1
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
        metrics_jobs=[{"userid": sub, "jobid": "job1"}, {"userid": "other", "jobid": "job9"}],
    )

    result = gcs.purge_user_data(sub, mock_config)

    assert result["deleted_objects"] == [
        f"users/{sub}/jobs/job1/data/train.csv",
        f"users/{sub}/user.json",
    ]
    assert result["deleted_bytes"] == 1050
    assert result["deleted_shared_run_ids"] == ["job1"]
    assert result["metrics_cache_entries_removed"] == 1
    # The blobs themselves were deleted, and the index entry was removed by path.
    assert "index/shared-runs/job1" in state["deleted"]
    # Only the other user's row survives in the rewritten cache.
    assert state["written"]["jobs"] == [{"userid": "other", "jobid": "job9"}]


def test_purge_user_data_dry_run_deletes_nothing(mock_config, mock_storage_client):
    _, bucket = mock_storage_client
    sub = "google-oauth2|123"
    user_blobs = [make_blob(f"users/{sub}/jobs/job1/data/train.csv", size=1000)]
    state = wire_bucket(
        bucket,
        user_blobs=user_blobs,
        index_entries={"job1": {"runid": "job1", "userid": sub}},
        metrics_jobs=[{"userid": sub, "jobid": "job1"}],
    )

    result = gcs.purge_user_data(sub, mock_config, dry_run=True)

    assert result["dry_run"] is True
    assert result["deleted_objects"] == [f"users/{sub}/jobs/job1/data/train.csv"]
    assert result["deleted_shared_run_ids"] == ["job1"]
    assert result["metrics_cache_entries_removed"] == 1
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


def test_purge_user_data_tolerates_missing_metrics_cache(mock_config, mock_storage_client):
    _, bucket = mock_storage_client
    sub = "google-oauth2|123"
    wire_bucket(bucket, user_blobs=[make_blob(f"users/{sub}/user.json")], metrics_jobs=None)

    result = gcs.purge_user_data(sub, mock_config)

    assert result["metrics_cache_entries_removed"] == 0


def test_purge_asta_workspace_data(monkeypatch):
    uuid = "00000000-0000-0000-0000-000000000000"
    blobs = [
        make_blob(f"owners/{uuid}/thread-a/data/train.csv", size=500),
        make_blob(f"owners/{uuid}/thread-b/data/test.csv", size=250),
    ]
    bucket = Mock()
    bucket.list_blobs.return_value = iter(blobs)
    client = Mock()
    client.bucket.return_value = bucket
    monkeypatch.setattr(asta_gcs.storage, "Client", lambda *a, **kw: client)

    result = asta_gcs.purge_asta_workspace_data(uuid)

    assert result["deleted_bytes"] == 750
    assert len(result["deleted_objects"]) == 2
    for blob in blobs:
        blob.delete.assert_called_once()


def test_summarize_asta_workspace_data_groups_threads(monkeypatch):
    uuid = "00000000-0000-0000-0000-000000000000"
    blobs = [
        make_blob(f"owners/{uuid}/thread-a/data/train.csv", size=500),
        make_blob(f"owners/{uuid}/thread-a/data/extra.csv", size=100),
        make_blob(f"owners/{uuid}/thread-b/data/test.csv", size=250),
    ]
    bucket = Mock()
    bucket.list_blobs.return_value = iter(blobs)
    client = Mock()
    client.bucket.return_value = bucket
    monkeypatch.setattr(asta_gcs.storage, "Client", lambda *a, **kw: client)

    summary = asta_gcs.summarize_asta_workspace_data(uuid)

    assert summary["object_count"] == 3
    assert summary["total_bytes"] == 850
    assert summary["thread_ids"] == ["thread-a", "thread-b"]


def test_asta_workspace_dry_run_deletes_nothing(monkeypatch):
    uuid = "00000000-0000-0000-0000-000000000000"
    blobs = [make_blob(f"owners/{uuid}/thread-a/data/train.csv", size=500)]
    bucket = Mock()
    bucket.list_blobs.return_value = iter(blobs)
    client = Mock()
    client.bucket.return_value = bucket
    monkeypatch.setattr(asta_gcs.storage, "Client", lambda *a, **kw: client)

    result = asta_gcs.purge_asta_workspace_data(uuid, dry_run=True)

    assert result["dry_run"] is True
    assert len(result["deleted_objects"]) == 1
    blobs[0].delete.assert_not_called()
