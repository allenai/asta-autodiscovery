"""Tests for data-library directories: keys, listing, job args, mounts, and forks."""

from unittest.mock import Mock, patch

import pytest
from autodiscovery_jobs import keys, persistence
from autodiscovery_jobs.backends import build_job_args
from autodiscovery_jobs.backends.docker import DockerBackend
from autodiscovery_jobs.config import JobConfig
from autodiscovery_jobs.manager import JobManager
from autodiscovery_jobs.run_details import RunDetails
from autodiscovery_jobs.storage import get_store

# ---------------------------------------------------------------------------
# Keys
# ---------------------------------------------------------------------------


def test_datalib_keys():
    assert keys.datalib_prefix("u1") == "users/u1/datalib/"
    assert keys.datalib_dir("u1", "census") == "users/u1/datalib/census"


@pytest.mark.parametrize("name", ["census", "cell atlas", "v1.2", "a_b-c"])
def test_validate_datalib_dirname_accepts_single_segments(name):
    assert keys.validate_datalib_dirname(name) == name


@pytest.mark.parametrize("name", ["", ".", "..", ".hidden", "a/b", "../x", "a\\b", "a\0b", None])
def test_validate_datalib_dirname_rejects_anything_else(name):
    with pytest.raises(ValueError):
        keys.validate_datalib_dirname(name)


# ---------------------------------------------------------------------------
# Listing (on the real local store)
# ---------------------------------------------------------------------------


@pytest.fixture
def populated_store(local_config):
    store = get_store(local_config)
    store.write_text("users/u1/datalib/census/README.md", "# Census\nHousehold survey.")
    store.write_text("users/u1/datalib/census/2020/part-0.csv", "a,b\n1,2\n")
    store.write_text("users/u1/datalib/atlas/cells.h5ad", "x")
    store.write_text("users/u1/datalib/.staging/ignored.txt", "x")
    store.write_text("users/u2/datalib/other/README.md", "someone else's")
    return local_config


def test_list_datalib_dirs(populated_store):
    dirs = persistence.list_datalib_dirs("u1", populated_store)

    assert [d.name for d in dirs] == ["atlas", "census"]
    assert dirs[0].description is None
    assert dirs[1].description == "# Census\nHousehold survey."


def test_list_datalib_dirs_truncates_readme(populated_store):
    dirs = persistence.list_datalib_dirs("u1", populated_store, max_description_chars=8)
    assert dirs[1].description == "# Census"


def test_list_datalib_dirs_empty_for_user_without_library(populated_store):
    assert persistence.list_datalib_dirs("nobody", populated_store) == []


def test_missing_datalib_dirs(populated_store):
    assert persistence.missing_datalib_dirs("u1", ["census", "atlas"], populated_store) == []
    assert persistence.missing_datalib_dirs("u1", ["census", "other"], populated_store) == ["other"]


def test_missing_datalib_dirs_rejects_traversal(populated_store):
    with pytest.raises(ValueError):
        persistence.missing_datalib_dirs("u1", ["../../u2/datalib/other"], populated_store)


# ---------------------------------------------------------------------------
# Job args
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code_backend", ["process", "local"])
def test_build_job_args_datalib_dirs_at_store_paths(code_backend):
    config = JobConfig(bucket="test-bucket", code_execution_backend=code_backend)

    args = build_job_args("u1", "j1", config, n_experiments=3, datalib_dirs=["census", "atlas"])

    assert "--datalib_dir=/mnt/data/users/u1/datalib/census" in args
    assert "--datalib_dir=/mnt/data/users/u1/datalib/atlas" in args
    assert not any(a.startswith("--datalib_dirs") for a in args)


def test_build_job_args_datalib_dirs_modal():
    config = JobConfig(bucket="test-bucket", code_execution_backend="modal")

    args = build_job_args("u1", "j1", config, n_experiments=3, datalib_dirs=["census"])

    # The job derives each directory's gs:// source from --bucket_path's bucket.
    assert "--datalib_dir=/mnt/data/users/u1/datalib/census" in args
    assert "--bucket_path=gs://test-bucket/users/u1/jobs/j1/data" in args


def test_build_job_args_without_datalib_is_unchanged():
    config = JobConfig(bucket="test-bucket", code_execution_backend="modal")

    assert build_job_args("u1", "j1", config, n_experiments=3) == build_job_args(
        "u1", "j1", config, n_experiments=3, datalib_dirs=[]
    )


def test_build_job_args_rejects_invalid_datalib_dir():
    with pytest.raises(ValueError):
        build_job_args("u1", "j1", JobConfig(), n_experiments=3, datalib_dirs=["../x"])


# ---------------------------------------------------------------------------
# Docker mounts
# ---------------------------------------------------------------------------


def test_docker_mounts_datalib_dirs_read_only(monkeypatch):
    monkeypatch.setenv("STORAGE_HOST_DIR", "/host/ad-data")
    config = JobConfig(
        backend="docker",
        storage_backend="local",
        storage_dir="/mnt/data",
        job_name="autodiscovery-job",
        job_image="autodiscovery:dev",
    )

    client = Mock()
    with patch("autodiscovery_jobs.backends.docker._docker_client", return_value=client):
        DockerBackend(config).run_job("u1", "j1", n_experiments=4, datalib_dirs=["census"])

    kwargs = client.containers.run.call_args.kwargs
    assert kwargs["volumes"]["/host/ad-data/users/u1/datalib/census"] == {
        "bind": "/mnt/data/users/u1/datalib/census",
        "mode": "ro",
    }
    # The run's own directory is still mounted read-write beside it.
    assert kwargs["volumes"]["/host/ad-data/users/u1/jobs/j1"]["mode"] == "rw"
    assert "--datalib_dir=/mnt/data/users/u1/datalib/census" in kwargs["command"]


# ---------------------------------------------------------------------------
# Forks
# ---------------------------------------------------------------------------

_PARENT = {"name": "Big run", "datasets": [], "datalib_dirs": ["census"], "n_experiments": 5}


def test_fork_metadata_keeps_datalib_dirs_for_the_owner():
    child = JobManager._build_fork_metadata(_PARENT, "p1", same_owner=True)
    assert child["datalib_dirs"] == ["census"]


def test_fork_metadata_drops_datalib_dirs_for_another_user():
    child = JobManager._build_fork_metadata(_PARENT, "p1", same_owner=False)
    assert child["datalib_dirs"] is None


def test_fork_of_datalib_only_run_needs_no_uploaded_data(mock_config):
    with (
        patch("autodiscovery_jobs.persistence.create_job_directory", return_value="uri"),
        patch("autodiscovery_jobs.persistence.has_data_files", return_value=False) as has_data,
        patch("autodiscovery_jobs.persistence.copy_job_data_files", return_value=[]),
        patch("autodiscovery_jobs.persistence.upload_metadata") as upload,
        patch(
            "autodiscovery_jobs.manager.create_run_details",
            return_value=RunDetails(execution_id=None, created_at="t", status="CREATED"),
        ),
    ):
        JobManager(mock_config).fork_job("p1", "owner", "owner", parent_metadata=_PARENT)

    has_data.assert_not_called()
    assert upload.call_args[0][2]["datalib_dirs"] == ["census"]
