"""Tests for managed local subprocess execution."""

from __future__ import annotations

import json
import stat
import sys
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from autodiscovery_jobs import JobManager
from autodiscovery_jobs.backends.local import LocalProcessBackend
from autodiscovery_jobs.config import JobConfig
from autodiscovery_jobs.local_runner import LocalProcessRunner
from autodiscovery_jobs.run_details import (
    create_run_details,
    get_run_details,
    update_run_details,
)


@pytest.fixture
def runner(tmp_path: Path) -> LocalProcessRunner:
    """Create a single-slot local runner in a temporary directory."""
    return LocalProcessRunner(JobConfig(local_root=str(tmp_path)))


def wait_for_phase(
    runner: LocalProcessRunner,
    execution_id: str,
    phases: set[str],
    timeout: float = 5,
) -> dict:
    """Wait for a test execution to enter one of the expected phases."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = runner.get_status(execution_id)
        if status["phase"] in phases:
            return status
        time.sleep(0.01)
    raise AssertionError(f"Execution did not reach {phases}")


def test_success_and_logs(runner: LocalProcessRunner, tmp_path: Path) -> None:
    """Persist successful completion and captured output."""
    execution_id = runner.start(
        [sys.executable, "-c", "print('completed')"],
        run_id="run-1",
        cwd=tmp_path / "work",
        log_path=tmp_path / "logs" / "run.log",
    )

    status = wait_for_phase(runner, execution_id, {"SUCCEEDED"})

    assert status["return_code"] == 0
    assert runner.get_logs(execution_id) == ["completed"]


def test_failure_is_persisted(runner: LocalProcessRunner, tmp_path: Path) -> None:
    """Persist a nonzero process exit as a failed execution."""
    execution_id = runner.start(
        [sys.executable, "-c", "raise SystemExit(7)"],
        run_id="run-1",
        cwd=tmp_path / "work",
        log_path=tmp_path / "logs" / "run.log",
    )

    status = wait_for_phase(runner, execution_id, {"FAILED"})

    assert status["return_code"] == 7


def test_cancel_and_concurrency_limit(runner: LocalProcessRunner, tmp_path: Path) -> None:
    """Cancel a process group and reject a second concurrent execution."""
    execution_id = runner.start(
        [sys.executable, "-c", "import time; time.sleep(30)"],
        run_id="run-1",
        cwd=tmp_path / "work-1",
        log_path=tmp_path / "logs" / "run-1.log",
    )
    with pytest.raises(RuntimeError, match="concurrency limit"):
        runner.start(
            [sys.executable, "-c", "print('second')"],
            run_id="run-2",
            cwd=tmp_path / "work-2",
            log_path=tmp_path / "logs" / "run-2.log",
        )

    runner.cancel(execution_id)
    status = wait_for_phase(runner, execution_id, {"CANCELLED"})

    assert status["phase"] == "CANCELLED"


def test_manager_builds_local_engine_command(tmp_path: Path) -> None:
    """Build the upstream engine command with local paths and provider options."""
    config = JobConfig(backend="local", local_root=str(tmp_path))
    manager = JobManager(config)
    manager.create_job("local", "run-1")
    source = tmp_path / "table.csv"
    source.write_text("value\n1\n", encoding="utf-8")
    manager.upload_dataset("local", "run-1", source)
    manager.upload_metadata(
        "local",
        "run-1",
        {"datasets": [{"name": "table.csv"}], "name": "Test run"},
    )
    manager.backend.runner.start = Mock(return_value="local-execution")

    execution_id = manager.run_job(
        "local",
        "run-1",
        n_experiments=2,
        model="claude-haiku-4.5",
        llm_provider="copilot",
        embedding_provider="copilot",
    )

    assert execution_id == "local-execution"
    command = manager.backend.runner.start.call_args.args[0]
    assert command[:3] == [sys.executable, "-m", "autodiscovery.local_worker"]
    assert "--backend=process" in command
    assert "--llm_provider=copilot" in command
    assert "--embedding_provider=copilot" in command
    runtime_metadata = tmp_path / "runs" / "run-1" / "work" / ".autodiscovery-metadata.json"
    assert runtime_metadata.is_file()
    runtime_datasets = json.loads(runtime_metadata.read_text(encoding="utf-8"))["datasets"]
    assert runtime_datasets[0]["name"] == "table.csv"
    alias = tmp_path / "runs" / "run-1" / "work" / "table.csv"
    assert alias.is_symlink()
    assert alias.read_text(encoding="utf-8") == "value\n1\n"
    assert not (tmp_path / "runs" / "run-1" / "data" / "table.csv").stat().st_mode & stat.S_IWUSR
    assert manager.get_metadata("local", "run-1")["name"] == "Test run"


def test_local_runtime_view_flattens_nested_declared_paths(tmp_path: Path) -> None:
    """Give base and threaded agents one stable basename for every declared local file."""
    run_path = tmp_path / "run"
    source = run_path / "data" / "study" / "nested" / "table.csv"
    source.parent.mkdir(parents=True)
    source.write_text("value\n1\n", encoding="utf-8")

    runtime_metadata = LocalProcessBackend._prepare_runtime_view(
        run_path, {"datasets": [{"name": "study/nested/table.csv"}]}
    )

    assert json.loads(runtime_metadata.read_text(encoding="utf-8"))["datasets"] == [
        {"name": "table.csv"}
    ]
    assert (run_path / "work" / "table.csv").resolve() == source.resolve()


def test_local_runtime_view_rejects_duplicate_basenames(tmp_path: Path) -> None:
    """Fail before model calls when flattening would make dataset paths ambiguous."""
    run_path = tmp_path / "run"
    for folder in ("first", "second"):
        source = run_path / "data" / folder / "table.csv"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(folder, encoding="utf-8")

    with pytest.raises(ValueError, match="filenames must be unique"):
        LocalProcessBackend._prepare_runtime_view(
            run_path,
            {"datasets": [{"name": "first/table.csv"}, {"name": "second/table.csv"}]},
        )


def test_local_run_details_round_trip(tmp_path: Path) -> None:
    """Persist local lifecycle state without creating a cloud client."""
    config = JobConfig(backend="local", local_root=str(tmp_path))
    manager = JobManager(config)
    manager.create_job("local", "run-1")

    created = create_run_details("local", "run-1", config)
    updated = update_run_details(
        "local",
        "run-1",
        {"execution_id": "local-123", "status": "RUNNING"},
        config,
    )

    assert created.status == "CREATED"
    assert updated.execution_id == "local-123"
    assert get_run_details("local", "run-1", config) == updated
