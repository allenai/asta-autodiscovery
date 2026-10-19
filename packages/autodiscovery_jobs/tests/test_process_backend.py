"""Tests for the host-process job backend."""

from __future__ import annotations

import json
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest
from autodiscovery_jobs import JobManager
from autodiscovery_jobs.backends import get_backend
from autodiscovery_jobs.backends.process import ProcessBackend
from autodiscovery_jobs.config import JobConfig
from autodiscovery_jobs.exceptions import JobBackendError


@pytest.fixture
def process_config(tmp_path: Path) -> JobConfig:
    """A process-backend configuration on a local store under ``tmp_path``."""
    return JobConfig(
        storage_backend="local",
        storage_dir=str(tmp_path / "store"),
        backend="process",
        job_name="test-job",
        process_job_dir=str(tmp_path / "executions"),
    )


def fake_engine(config: JobConfig) -> JobConfig:
    """Return ``config`` with the engine replaced by the Python in ``$SCRIPT``.

    The backend runs ``<python> -m autodiscovery.run <args>``; a wrapper standing
    in for the interpreter ignores those and runs the inline script instead.
    """
    wrapper = Path(config.process_job_dir).parent / "fake-python"
    wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" -c "$SCRIPT"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    return replace(config, process_job_python=str(wrapper))


def launch(config: JobConfig, script: str, monkeypatch) -> tuple[ProcessBackend, str]:
    monkeypatch.setenv("SCRIPT", script)
    backend = ProcessBackend(fake_engine(config))
    return backend, backend.run_job("testuser", "job1", n_experiments=2)


def wait_for_phase(backend: ProcessBackend, execution_id: str, phase: str, timeout=10) -> dict:
    deadline = time.monotonic() + timeout
    status: dict = {}
    while time.monotonic() < deadline:
        status = backend.get_job_status(execution_id)
        if status["phase"] == phase:
            return status
        time.sleep(0.02)
    raise AssertionError(f"Execution did not reach {phase}: {status}")


def test_get_backend_process(process_config):
    assert isinstance(get_backend(process_config), ProcessBackend)


def test_run_job_runs_the_engine_on_the_store_in_place(process_config, monkeypatch):
    """The job gets the shared args, rooted at the local store instead of a mount."""
    backend, execution_id = launch(
        process_config, "import sys; print(' '.join(sys.argv[1:]))", monkeypatch
    )

    state = json.loads(
        (Path(process_config.process_job_dir) / execution_id / "state.json").read_text()
    )
    command = state["command"]
    store = Path(process_config.storage_dir).resolve()
    assert command[1:3] == ["-m", "autodiscovery.run"]
    assert f"--dataset_metadata={store}/users/testuser/jobs/job1/metadata.json" in command
    assert f"--out_dir={store}/users/testuser/jobs/job1/output" in command
    assert "--model=openai/test-model" in command
    assert execution_id.startswith("test-job-")
    wait_for_phase(backend, execution_id, "SUCCEEDED")


def test_success_and_logs(process_config, monkeypatch):
    backend, execution_id = launch(process_config, "print('completed')", monkeypatch)

    status = wait_for_phase(backend, execution_id, "SUCCEEDED")

    assert status["exit_code"] == 0
    assert status["completion_time"]
    assert backend.get_job_logs(execution_id) == ["completed"]


def test_job_runs_in_its_own_working_directory(process_config, monkeypatch):
    backend, execution_id = launch(process_config, "import os; print(os.getcwd())", monkeypatch)

    wait_for_phase(backend, execution_id, "SUCCEEDED")

    work_dir = Path(process_config.process_job_dir).resolve() / execution_id / "work"
    assert backend.get_job_logs(execution_id) == [str(work_dir)]


def test_failure_is_reported(process_config, monkeypatch):
    backend, execution_id = launch(process_config, "raise SystemExit(7)", monkeypatch)

    status = wait_for_phase(backend, execution_id, "FAILED")

    assert status["exit_code"] == 7


def test_status_survives_a_new_backend_instance(process_config, monkeypatch):
    """Another API worker, or a restarted API, reads the same status from disk."""
    backend, execution_id = launch(process_config, "print('done')", monkeypatch)
    wait_for_phase(backend, execution_id, "SUCCEEDED")

    other = ProcessBackend(process_config)

    assert other.get_job_status(execution_id)["phase"] == "SUCCEEDED"
    assert other.get_job_logs(execution_id) == ["done"]


def test_a_process_that_vanished_is_failed(process_config, monkeypatch):
    """A job killed from outside leaves no exit status, and is not left RUNNING."""
    backend, execution_id = launch(process_config, "import time; time.sleep(30)", monkeypatch)
    state_path = Path(process_config.process_job_dir) / execution_id / "state.json"
    original = state_path.read_text()
    state_path.write_text(json.dumps({**json.loads(original), "pid": 2**22 + 12345}))

    assert backend.get_job_status(execution_id)["phase"] == "FAILED"

    state_path.write_text(original)
    backend.cancel_job(execution_id)


def test_cancel_and_concurrency_limit(process_config, monkeypatch):
    backend, execution_id = launch(process_config, "import time; time.sleep(30)", monkeypatch)
    wait_for_phase(backend, execution_id, "RUNNING")

    with pytest.raises(JobBackendError, match="already running"):
        backend.run_job("testuser", "job2", n_experiments=2)

    backend.cancel_job(execution_id)
    status = backend.get_job_status(execution_id)

    assert status["phase"] == "CANCELLED"
    assert status["completion_time"]
    # The slot is free again.
    second = backend.run_job("testuser", "job2", n_experiments=2)
    backend.cancel_job(second)


def test_cancel_after_completion_is_a_no_op(process_config, monkeypatch):
    backend, execution_id = launch(process_config, "print('done')", monkeypatch)
    wait_for_phase(backend, execution_id, "SUCCEEDED")

    backend.cancel_job(execution_id)

    assert backend.get_job_status(execution_id)["phase"] == "SUCCEEDED"


def test_unknown_and_unsafe_execution_ids(process_config):
    backend = ProcessBackend(process_config)

    with pytest.raises(JobBackendError, match="not found"):
        backend.get_job_status("test-job-missing")
    with pytest.raises(JobBackendError, match="Invalid execution ID"):
        backend.get_job_status("../escape")
    assert backend.get_job_logs(None) == []


def test_requires_an_interpreter_with_the_engine(process_config, monkeypatch):
    monkeypatch.setattr(
        "autodiscovery_jobs.backends.process.importlib.util.find_spec", lambda name: None
    )

    with pytest.raises(JobBackendError, match="PROCESS_JOB_PYTHON"):
        ProcessBackend(process_config).run_job("testuser", "job1", n_experiments=2)


def test_manager_runs_jobs_through_the_process_backend(process_config, monkeypatch):
    monkeypatch.setenv("SCRIPT", "print('via manager')")
    manager = JobManager(fake_engine(process_config))
    manager.create_job("testuser", "job1")

    execution_id = manager.run_job("testuser", "job1", n_experiments=1)

    assert wait_for_phase(manager.backend, execution_id, "SUCCEEDED")
    assert manager.get_job_logs(execution_id) == ["via manager"]


def test_config_reads_process_settings_from_the_environment(monkeypatch):
    monkeypatch.setenv("PROCESS_JOB_DIR", "/tmp/ad-jobs")
    monkeypatch.setenv("PROCESS_JOB_PYTHON", "/opt/ad/bin/python")
    monkeypatch.setenv("PROCESS_MAX_CONCURRENT_JOBS", "3")

    config = JobConfig.from_env()

    assert config.process_job_dir == "/tmp/ad-jobs"
    assert config.process_job_python == "/opt/ad/bin/python"
    assert config.process_max_concurrent_jobs == 3
