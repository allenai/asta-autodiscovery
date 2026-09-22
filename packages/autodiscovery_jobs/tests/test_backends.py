"""Tests for the job backend factory, shared arg builder, and Docker backend."""

from unittest.mock import Mock, patch

import pytest
from autodiscovery_jobs.backends import build_job_args, get_backend
from autodiscovery_jobs.backends.docker import DockerBackend, _phase_from_state
from autodiscovery_jobs.backends.gcp import CloudRunBackend
from autodiscovery_jobs.config import JobConfig
from autodiscovery_jobs.exceptions import DockerBackendError, JobBackendError

# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_get_backend_gcp(mock_config):
    assert isinstance(get_backend(mock_config), CloudRunBackend)


def test_get_backend_docker():
    config = JobConfig(backend="docker", bucket="test-bucket", job_image="ad:dev")
    assert isinstance(get_backend(config), DockerBackend)


def test_get_backend_default_is_docker():
    # backend unset -> the JobConfig default (docker) is used.
    assert isinstance(get_backend(JobConfig(bucket="test-bucket")), DockerBackend)


def test_get_backend_case_insensitive():
    config = JobConfig(backend="Docker", bucket="b", job_image="ad:dev")
    assert isinstance(get_backend(config), DockerBackend)


def test_get_backend_unknown():
    config = JobConfig(backend="nope")
    with pytest.raises(JobBackendError):
        get_backend(config)


# ---------------------------------------------------------------------------
# Shared arg builder (backend-agnostic parity)
# ---------------------------------------------------------------------------


def test_build_job_args_required(mock_config):
    # mock_config leaves code_execution_backend at its default ("process").
    args = build_job_args("testuser", "job1", mock_config, n_experiments=4, model="gpt-4o")

    assert "--dataset_metadata=/mnt/gcs/users/testuser/jobs/job1/metadata.json" in args
    assert "--out_dir=/mnt/gcs/users/testuser/jobs/job1/output" in args
    assert "--n_experiments=4" in args
    assert "--backend=process" in args
    assert "--no-timestamp_dir" in args
    assert "--model=gpt-4o" in args
    # bucket_path / modal flag are modal-only
    assert not any(a.startswith("--bucket_path=") for a in args)


@pytest.mark.parametrize(
    "code_backend,expects_bucket_path",
    [("process", False), ("local", False), ("modal", True)],
)
def test_build_job_args_code_execution_backend(code_backend, expects_bucket_path):
    config = JobConfig(bucket="test-bucket", code_execution_backend=code_backend)
    args = build_job_args("u", "j", config, n_experiments=1)

    assert f"--backend={code_backend}" in args
    has_bucket_path = any(a.startswith("--bucket_path=") for a in args)
    assert has_bucket_path is expects_bucket_path
    if expects_bucket_path:
        assert "--bucket_path=gs://test-bucket/users/u/jobs/j/data" in args


def test_build_job_args_rejects_unknown_code_backend():
    config = JobConfig(bucket="b", code_execution_backend="wasm")
    with pytest.raises(JobBackendError):
        build_job_args("u", "j", config, n_experiments=1)


def test_build_job_args_requires_n_experiments(mock_config):
    with pytest.raises(JobBackendError):
        build_job_args("testuser", "job1", mock_config)


def test_build_job_args_boolean_kwargs(mock_config):
    args = build_job_args("u", "j", mock_config, n_experiments=1, some_flag=True, other=False)
    assert "--some_flag" in args
    assert "--no-other" in args


# ---------------------------------------------------------------------------
# Docker backend
# ---------------------------------------------------------------------------


@pytest.fixture
def docker_config():
    """Docker job backend over the gcs store (job container gcsfuse-mounts it)."""
    return JobConfig(
        backend="docker",
        storage_backend="gcs",
        bucket="test-bucket",
        job_name="autodiscovery-job",
        job_image="autodiscovery:dev",
    )


@pytest.fixture
def docker_local_config():
    """Docker job backend over the local store (job container bind-mounts it)."""
    return JobConfig(
        backend="docker",
        storage_backend="local",
        storage_dir="/mnt/data",
        job_name="autodiscovery-job",
        job_image="autodiscovery:dev",
    )


def test_docker_run_job_launches_container(docker_config, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("MODAL_TOKEN_ID", "tok")
    monkeypatch.setenv("GCP_KEY_HOST_PATH", "/host/secrets/gcp-key.json")

    client = Mock()
    with patch("autodiscovery_jobs.backends.docker._docker_client", return_value=client):
        backend = DockerBackend(docker_config)
        execution_id = backend.run_job("testuser", "job1", n_experiments=4, model="gpt-4o")

    assert execution_id.startswith("autodiscovery-job-")
    client.containers.run.assert_called_once()
    kwargs = client.containers.run.call_args.kwargs
    assert kwargs["image"] == "autodiscovery:dev"
    assert kwargs["name"] == execution_id
    assert kwargs["detach"] is True
    assert "--n_experiments=4" in kwargs["command"]
    assert "--model=gpt-4o" in kwargs["command"]
    # gcsfuse trigger + credentials forwarded
    assert kwargs["environment"]["GCSFUSE_BUCKET"] == "test-bucket"
    # mount is scoped to this job's own prefix (keeps other users' data out)
    assert kwargs["environment"]["GCSFUSE_ONLY_DIR"] == "users/testuser/jobs/job1"
    assert kwargs["environment"]["OPENAI_API_KEY"] == "sk-test"
    assert kwargs["environment"]["MODAL_TOKEN_ID"] == "tok"
    assert kwargs["environment"]["GOOGLE_APPLICATION_CREDENTIALS"] == "/secrets/gcp-key.json"
    # fuse device + capability for gcsfuse
    assert "/dev/fuse" in kwargs["devices"]
    assert "SYS_ADMIN" in kwargs["cap_add"]
    # host credentials bind-mounted into the job container
    assert "/host/secrets/gcp-key.json" in kwargs["volumes"]


def test_docker_run_job_bind_mounts_local_store(docker_local_config, monkeypatch):
    monkeypatch.setenv("STORAGE_HOST_DIR", "/host/ad-data")

    client = Mock()
    with patch("autodiscovery_jobs.backends.docker._docker_client", return_value=client):
        DockerBackend(docker_local_config).run_job("testuser", "job1", n_experiments=4)

    kwargs = client.containers.run.call_args.kwargs
    # The run's own host subtree is mounted where the job args expect it, so the
    # command is identical to the gcsfuse case.
    assert kwargs["volumes"] == {
        "/host/ad-data/users/testuser/jobs/job1": {
            "bind": "/mnt/gcs/users/testuser/jobs/job1",
            "mode": "rw",
        }
    }
    assert "--dataset_metadata=/mnt/gcs/users/testuser/jobs/job1/metadata.json" in kwargs[
        "command"
    ]
    # No gcsfuse, so none of its privileges or triggers.
    assert "GCSFUSE_BUCKET" not in kwargs["environment"]
    assert kwargs["devices"] == []
    assert kwargs["cap_add"] == []
    assert kwargs["security_opt"] == []


def test_docker_local_store_falls_back_to_storage_dir(docker_local_config, monkeypatch):
    """Without STORAGE_HOST_DIR the API isn't containerized, so storage_dir is a host path."""
    monkeypatch.delenv("STORAGE_HOST_DIR", raising=False)

    client = Mock()
    with patch("autodiscovery_jobs.backends.docker._docker_client", return_value=client):
        DockerBackend(docker_local_config).run_job("testuser", "job1", n_experiments=1)

    volumes = client.containers.run.call_args.kwargs["volumes"]
    assert "/mnt/data/users/testuser/jobs/job1" in volumes


def test_docker_local_store_requires_absolute_host_dir(monkeypatch):
    monkeypatch.setenv("STORAGE_HOST_DIR", "./data")
    config = JobConfig(backend="docker", storage_backend="local", job_image="ad:dev")

    client = Mock()
    with patch("autodiscovery_jobs.backends.docker._docker_client", return_value=client):
        with pytest.raises(DockerBackendError, match="absolute"):
            DockerBackend(config).run_job("u", "j", n_experiments=1)


def test_docker_run_job_requires_image(monkeypatch):
    config = JobConfig(backend="docker", bucket="b", job_image=None)
    client = Mock()
    with patch("autodiscovery_jobs.backends.docker._docker_client", return_value=client):
        backend = DockerBackend(config)
        with pytest.raises(DockerBackendError):
            backend.run_job("u", "j", n_experiments=1)


@pytest.mark.parametrize(
    "status,exit_code,expected",
    [
        ("running", 0, "RUNNING"),
        ("created", 0, "PENDING"),
        ("exited", 0, "SUCCEEDED"),
        ("exited", 1, "FAILED"),
        ("dead", 0, "FAILED"),
    ],
)
def test_phase_from_state(status, exit_code, expected):
    assert _phase_from_state(status, exit_code) == expected


def test_docker_get_job_status(docker_config):
    container = Mock()
    container.attrs = {
        "Created": "2024-01-01T00:00:00Z",
        "State": {
            "Status": "exited",
            "ExitCode": 0,
            "StartedAt": "2024-01-01T00:00:01Z",
            "FinishedAt": "2024-01-01T00:05:00Z",
        },
    }
    client = Mock()
    client.containers.get.return_value = container
    with patch("autodiscovery_jobs.backends.docker._docker_client", return_value=client):
        status = DockerBackend(docker_config).get_job_status("autodiscovery-job-abc12345")

    assert status["phase"] == "SUCCEEDED"
    assert status["completion_time"] == "2024-01-01T00:05:00Z"


def test_docker_get_job_status_zero_time_normalized(docker_config):
    container = Mock()
    container.attrs = {
        "Created": "2024-01-01T00:00:00Z",
        "State": {
            "Status": "running",
            "ExitCode": 0,
            "StartedAt": "2024-01-01T00:00:01Z",
            "FinishedAt": "0001-01-01T00:00:00Z",
        },
    }
    client = Mock()
    client.containers.get.return_value = container
    with patch("autodiscovery_jobs.backends.docker._docker_client", return_value=client):
        status = DockerBackend(docker_config).get_job_status("autodiscovery-job-abc12345")

    assert status["phase"] == "RUNNING"
    assert status["completion_time"] is None


def test_docker_cancel_job(docker_config):
    container = Mock()
    client = Mock()
    client.containers.get.return_value = container
    with patch("autodiscovery_jobs.backends.docker._docker_client", return_value=client):
        DockerBackend(docker_config).cancel_job("autodiscovery-job-abc12345")
    container.stop.assert_called_once()


def test_docker_get_job_logs(docker_config):
    container = Mock()
    container.logs.return_value = b"line1\nline2\n\nline3\n"
    client = Mock()
    client.containers.get.return_value = container
    with patch("autodiscovery_jobs.backends.docker._docker_client", return_value=client):
        logs = DockerBackend(docker_config).get_job_logs("autodiscovery-job-abc12345", limit=10)
    assert logs == ["line1", "line2", "line3"]


def test_docker_get_job_logs_no_execution_id(docker_config):
    with patch("autodiscovery_jobs.backends.docker._docker_client") as mock_client:
        logs = DockerBackend(docker_config).get_job_logs(None)
    assert logs == []
    mock_client.assert_not_called()
