"""Tests for the job-data persistence API.

These run against the default filesystem store on a real temp directory, so the
key layout, listings, and exception contract are exercised end to end rather than
asserted against a mocked client. The backend under the API is swappable and
separately covered by ``test_storage.py``.
"""

import json

import pytest
from autodiscovery_jobs import persistence
from autodiscovery_jobs.exceptions import JobAlreadyExistsError, JobNotFoundError


@pytest.fixture
def job(local_config):
    """Create a run with data/ and output/ placeholders, as the API does."""
    persistence.create_job_directory("testuser", "job1", local_config)
    return local_config


def test_parse_gcs_path():
    """GCS URI parsing (still used for gs:// preloaded dataset sources)."""
    # With gs:// prefix
    bucket, prefix = persistence.parse_gcs_path("gs://my-bucket/path/to/data")
    assert bucket == "my-bucket"
    assert prefix == "path/to/data/"

    # Without gs:// prefix
    bucket, prefix = persistence.parse_gcs_path("my-bucket/path/to/data/")
    assert bucket == "my-bucket"
    assert prefix == "path/to/data/"

    # Just bucket
    bucket, prefix = persistence.parse_gcs_path("gs://my-bucket")
    assert bucket == "my-bucket"
    assert prefix == ""


def test_paths_use_the_active_backend_uri(local_config, mock_config):
    assert persistence.get_user_path("testuser", local_config).startswith("file:///")
    assert persistence.get_user_path("testuser", local_config).endswith("/users/testuser/")

    assert (
        persistence.get_job_path("testuser", "job1", mock_config)
        == "gs://test-bucket/users/testuser/jobs/job1/"
    )


def test_create_job_directory(local_config):
    path = persistence.create_job_directory("testuser", "newjob", local_config)

    assert path.endswith("/users/testuser/jobs/newjob/")
    assert persistence.job_exists("testuser", "newjob", local_config) is True
    # Placeholders establish data/ and output/ (prefixes have no other existence).
    keys = {info.key for info in _list(local_config, "users/testuser/jobs/newjob/")}
    assert keys == {
        "users/testuser/jobs/newjob/data/.placeholder",
        "users/testuser/jobs/newjob/output/.placeholder",
    }


def test_job_exists_false_for_unknown_job(local_config):
    assert persistence.job_exists("testuser", "nope", local_config) is False


def test_create_job_directory_already_exists(job):
    with pytest.raises(JobAlreadyExistsError):
        persistence.create_job_directory("testuser", "job1", job)


def test_create_job_directory_overwrite(job):
    persistence.create_job_directory("testuser", "job1", job, overwrite=True)


def test_list_user_ids_and_jobs(local_config):
    persistence.create_job_directory("alice", "job1", local_config)
    persistence.create_job_directory("alice", "job2", local_config)
    persistence.create_job_directory("bob", "job3", local_config)

    assert persistence.list_user_ids(local_config) == ["alice", "bob"]
    assert persistence.list_user_jobs("alice", local_config) == ["job1", "job2"]
    assert persistence.list_user_jobs("nobody", local_config) == []


def test_metadata_round_trip(job):
    metadata = {"name": "My run", "datasets": [{"name": "test.csv"}]}
    path = persistence.upload_metadata("testuser", "job1", metadata, job)

    assert path.endswith("/users/testuser/jobs/job1/metadata.json")
    assert persistence.get_metadata("testuser", "job1", job) == metadata


def test_upload_metadata_requires_existing_job(local_config):
    with pytest.raises(JobNotFoundError):
        persistence.upload_metadata("testuser", "ghost", {}, local_config)


def test_get_metadata_missing_job_raises_not_found(local_config):
    with pytest.raises(JobNotFoundError):
        persistence.get_metadata("testuser", "ghost", local_config)


def test_job_args_round_trip(job):
    assert persistence.get_job_args("testuser", "job1", job) is None

    persistence.upload_job_args("testuser", "job1", {"n_experiments": 4}, job)
    assert persistence.get_job_args("testuser", "job1", job) == {"n_experiments": 4}


def test_upload_dataset_file(job, tmp_path):
    src = tmp_path / "data.csv"
    src.write_text("col1,col2\n1,2")

    path = persistence.upload_dataset("testuser", "job1", src, job)

    assert path.endswith("/users/testuser/jobs/job1/data/")
    assert persistence.has_data_files("testuser", "job1", job) is True
    keys = {info.key for info in _list(job, "users/testuser/jobs/job1/data/")}
    assert "users/testuser/jobs/job1/data/data.csv" in keys


def test_upload_dataset_directory(job, tmp_path):
    src = tmp_path / "bundle"
    (src / "nested").mkdir(parents=True)
    (src / "a.csv").write_text("a")
    (src / "nested" / "b.csv").write_text("b")

    persistence.upload_dataset("testuser", "job1", src, job)

    keys = {info.key for info in _list(job, "users/testuser/jobs/job1/data/")}
    assert "users/testuser/jobs/job1/data/a.csv" in keys
    assert "users/testuser/jobs/job1/data/nested/b.csv" in keys


def test_upload_dataset_remote_name(job, tmp_path):
    src = tmp_path / "tmpXYZ"
    src.write_text("a")

    persistence.upload_dataset("testuser", "job1", src, job, remote_name="real.csv")

    assert {info.key for info in _list(job, "users/testuser/jobs/job1/data/real.csv")} == {
        "users/testuser/jobs/job1/data/real.csv"
    }


def test_has_data_files_ignores_placeholder(job):
    assert persistence.has_data_files("testuser", "job1", job) is False


def test_copy_job_data_files(job, tmp_path):
    src = tmp_path / "data.csv"
    src.write_text("col1\n1")
    persistence.upload_dataset("testuser", "job1", src, job)
    persistence.create_job_directory("other", "job2", job)

    copied = persistence.copy_job_data_files("testuser", "job1", "other", "job2", job)

    assert copied == ["data.csv"]
    assert persistence.has_data_files("other", "job2", job) is True


def test_delete_job_directory(job):
    persistence.delete_job_directory("testuser", "job1", job)
    assert persistence.job_exists("testuser", "job1", job) is False


def test_delete_job_directory_not_found(local_config):
    with pytest.raises(JobNotFoundError):
        persistence.delete_job_directory("testuser", "ghost", local_config)


def test_soft_delete_job_preserves_results(job, tmp_path):
    src = tmp_path / "data.csv"
    src.write_text("col1\n1")
    persistence.upload_dataset("testuser", "job1", src, job)
    persistence.upload_metadata("testuser", "job1", {"name": "run"}, job)
    _write(job, "users/testuser/jobs/job1/output/mcts_node_0_1.json", {"id": "node_0_1"})

    result = persistence.soft_delete_job("testuser", "job1", job)

    assert result["status"] == "DELETED"
    assert len(result["deleted_files"]) == 1
    # Uploaded data is gone; metadata and results survive.
    assert persistence.has_data_files("testuser", "job1", job) is False
    assert persistence.get_metadata("testuser", "job1", job) == {"name": "run"}
    assert persistence.list_experiment_files("testuser", "job1", job) == [
        "mcts_node_0_1.json"
    ]

    # Idempotent.
    persistence.soft_delete_job("testuser", "job1", job)


def test_expire_datasets_respects_age(job, tmp_path):
    src = tmp_path / "data.csv"
    src.write_text("col1\n1")
    persistence.upload_dataset("testuser", "job1", src, job)

    # Freshly written, so nothing is old enough to expire yet.
    assert persistence.expire_datasets("testuser", "job1", 7, dry_run=False, config=job) == []

    expired = persistence.expire_datasets("testuser", "job1", 0, dry_run=True, config=job)
    assert len(expired) == 1
    assert persistence.has_data_files("testuser", "job1", job) is True  # dry run

    persistence.expire_datasets("testuser", "job1", 0, dry_run=False, config=job)
    assert persistence.has_data_files("testuser", "job1", job) is False


def test_get_job_results_excludes_placeholder(job):
    _write(job, "users/testuser/jobs/job1/output/result1.json", {})
    _write(job, "users/testuser/jobs/job1/output/result2.json", {})

    results = persistence.get_job_results("testuser", "job1", job)

    assert len(results) == 2
    assert all(".placeholder" not in r for r in results)


def test_download_job_results(job, tmp_path):
    _write(job, "users/testuser/jobs/job1/output/result.json", {"ok": True})
    _write(job, "users/testuser/jobs/job1/output/rich_outputs/ro_0_1.json", [])

    local_dir = tmp_path / "results"
    paths = persistence.download_job_results("testuser", "job1", local_dir, job)

    assert {p.relative_to(local_dir).as_posix() for p in paths} == {
        "result.json",
        "rich_outputs/ro_0_1.json",
    }
    assert json.loads((local_dir / "result.json").read_text()) == {"ok": True}


def test_experiment_files_exclude_root_node(job):
    _write(job, "users/testuser/jobs/job1/output/mcts_node_1_0.json", {})  # root node
    _write(job, "users/testuser/jobs/job1/output/mcts_node_0_1.json", {})
    _write(job, "users/testuser/jobs/job1/output/mcts_node_2_3.json", {})
    _write(job, "users/testuser/jobs/job1/output/args.json", {})

    assert persistence.list_experiment_files("testuser", "job1", job) == [
        "mcts_node_0_1.json",
        "mcts_node_2_3.json",
    ]
    assert persistence.count_experiment_results("testuser", "job1", job) == 2


def test_read_experiment_node(job):
    _write(job, "users/testuser/jobs/job1/output/mcts_node_0_1.json", {"id": "node_0_1"})

    assert persistence.read_experiment_node(
        "testuser", "job1", "mcts_node_0_1.json", job
    ) == {"id": "node_0_1"}
    assert persistence.read_experiment_node("testuser", "job1", "nope.json", job) is None


def test_read_rich_outputs(job):
    _write(
        job,
        "users/testuser/jobs/job1/output/rich_outputs/ro_0_1.json",
        [{"text/plain": "hi"}],
    )

    assert persistence.read_rich_outputs("testuser", "job1", 0, 1, job) == [
        {"text/plain": "hi"}
    ]
    # Missing and malformed payloads degrade to an empty list.
    assert persistence.read_rich_outputs("testuser", "job1", 9, 9, job) == []
    _write(job, "users/testuser/jobs/job1/output/rich_outputs/ro_2_2.json", {"not": "a list"})
    assert persistence.read_rich_outputs("testuser", "job1", 2, 2, job) == []


def test_shared_run_index_round_trip(job):
    assert persistence.get_shared_run_index("job1", job) is None

    persistence.write_shared_run_index("job1", "testuser", job)
    assert persistence.get_shared_run_index("job1", job) == "testuser"

    persistence.delete_shared_run_index("job1", job)
    assert persistence.get_shared_run_index("job1", job) is None
    # Deleting a missing entry is a no-op.
    persistence.delete_shared_run_index("job1", job)


def test_get_userid_for_job_scans_all_users(job):
    persistence.upload_metadata("testuser", "job1", {"name": "run"}, job)
    persistence.create_job_directory("other", "job2", job)
    persistence.upload_metadata("other", "job2", {"name": "run2"}, job)

    assert persistence.get_userid_for_job("job2", job) == "other"
    assert persistence.get_userid_for_job("job1", job) == "testuser"
    assert persistence.get_userid_for_job("nope", job) is None


def test_generate_upload_url_without_presigning(job):
    result = persistence.generate_upload_url("testuser", "job1", "data.csv", "text/csv", 60, job)

    # The filesystem store cannot issue capability URLs; the API receives the
    # upload itself and writes it to the returned key.
    assert result["upload_url"] is None
    assert result["key"] == "users/testuser/jobs/job1/data/data.csv"
    assert result["storage_path"].endswith("/users/testuser/jobs/job1/data/data.csv")


def test_generate_upload_url_requires_existing_job(local_config):
    with pytest.raises(JobNotFoundError):
        persistence.generate_upload_url("testuser", "ghost", "d.csv", "text/csv", 60, local_config)


def test_dataset_key():
    assert persistence.dataset_key("u", "j", "a.csv") == "users/u/jobs/j/data/a.csv"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _list(config, prefix):
    from autodiscovery_jobs.storage import get_store

    return list(get_store(config).list(prefix))


def _write(config, key, payload):
    from autodiscovery_jobs.storage import get_store

    get_store(config).write_text(key, json.dumps(payload))
