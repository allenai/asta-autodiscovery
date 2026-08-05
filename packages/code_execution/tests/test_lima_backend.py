from __future__ import annotations

import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

import pytest

from code_execution import LimaIPythonBackend


def _backend(tmp_path: Path) -> tuple[LimaIPythonBackend, Path, Path, Path]:
    lima_path = tmp_path / "limactl"
    lima_path.touch()
    lima_home = tmp_path / "lima-home"
    source = tmp_path / "source" / "dataset.csv"
    source.parent.mkdir()
    source.write_text("value\n1\n", encoding="utf-8")
    work = tmp_path / "work"
    thread = work / "thread_1"
    thread.mkdir(parents=True)
    return (
        LimaIPythonBackend(
            cwd=str(thread),
            dataset_paths=[str(source)],
            lima_path=str(lima_path),
            lima_home=str(lima_home),
        ),
        source,
        work,
        lima_home,
    )


def test_run_cell_uses_exact_mounts_and_hardened_service(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, source, work, _ = _backend(tmp_path)
    calls: list[tuple[list[str], dict[str, Any]]] = []
    response = {
        "stdout": "ok\n",
        "stderr": "",
        "rich_outputs": [],
        "success": True,
        "error": None,
    }

    def fake_run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((arguments, kwargs))
        stdout = json.dumps(response) if "systemd-run" in arguments else ""
        return subprocess.CompletedProcess(arguments, 0, stdout=stdout, stderr="")

    monkeypatch.setattr("code_execution.lima_backend.subprocess.run", fake_run)

    result = backend.run_cell("print('ok')", timeout_s=15)

    assert result == response
    edit = next(arguments for arguments, _ in calls if "edit" in arguments)
    assert edit[1:3] == ["edit", "ad"]
    assert f"--mount-only={source.parent},{work}:w" in edit
    assert "--mount-type=virtiofs" in edit

    service = next(arguments for arguments, _ in calls if "systemd-run" in arguments)
    assert "PrivateNetwork=yes" in service
    assert "RestrictAddressFamilies=AF_UNIX" in service
    assert "NoNewPrivileges=yes" in service
    assert "ProtectSystem=strict" in service
    assert "ProtectHome=yes" in service
    assert "ProtectKernelTunables=yes" in service
    assert "ProtectKernelModules=yes" in service
    assert "ProtectKernelLogs=yes" in service
    assert "ProtectControlGroups=yes" in service
    assert "ProtectClock=yes" in service
    assert "ProtectHostname=yes" in service
    assert "LockPersonality=yes" in service
    assert "RestrictRealtime=yes" in service
    assert "DevicePolicy=closed" in service
    assert "UMask=0077" in service
    assert "TasksMax=2048" in service
    assert "LimitNOFILE=4096" in service
    assert "MemorySwapMax=0" in service
    assert "MemoryMax=90%" in service
    assert "CapabilityBoundingSet=" in service
    assert f"InaccessiblePaths={json.dumps(str(source.parent))}" in service
    assert f"InaccessiblePaths={json.dumps(str(work))}" in service
    assert f"BindPaths={json.dumps(str(work / 'thread_1'))}:" in " ".join(service)
    assert f"BindReadOnlyPaths={json.dumps(str(source))}:" in " ".join(service)
    assert all("/Users" not in value for value in service if value.startswith("WorkingDirectory="))


def test_matching_running_vm_reuses_mounts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, source, work, lima_home = _backend(tmp_path)
    instance = lima_home / "ad"
    instance.mkdir(parents=True)
    (instance / ".autodiscovery-mounts.json").write_text(
        json.dumps(
            {
                "dataset_roots": [str(source.parent)],
                "work_root": str(work),
            }
        ),
        encoding="utf-8",
    )
    calls: list[list[str]] = []
    response = {
        "stdout": "",
        "stderr": "",
        "rich_outputs": [],
        "success": True,
        "error": None,
    }

    def fake_run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        if "list" in arguments:
            return subprocess.CompletedProcess(
                arguments, 0, stdout='{"status": "Running"}', stderr=""
            )
        stdout = json.dumps(response) if "systemd-run" in arguments else ""
        return subprocess.CompletedProcess(arguments, 0, stdout=stdout, stderr="")

    monkeypatch.setattr("code_execution.lima_backend.subprocess.run", fake_run)

    assert backend.run_cell("pass")["success"] is True
    assert not any("edit" in arguments for arguments in calls)
    assert not any("start" in arguments for arguments in calls)
    assert not any("stop" in arguments for arguments in calls)


def test_timeout_is_normalized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    backend, _, _, _ = _backend(tmp_path)

    def fake_run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "systemd-run" in arguments:
            raise subprocess.TimeoutExpired(arguments, kwargs.get("timeout", 0))
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")

    monkeypatch.setattr("code_execution.lima_backend.subprocess.run", fake_run)

    result = backend.run_cell("pass", timeout_s=2)

    assert result["success"] is False
    assert result["error"]["type"] == "TimeoutError"
    assert "2s" in result["error"]["message"]


def test_invalid_vm_output_is_normalized(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, _, _, _ = _backend(tmp_path)

    def fake_run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        stdout = "not-json" if "systemd-run" in arguments else ""
        return subprocess.CompletedProcess(arguments, 1, stdout=stdout, stderr="service failed")

    monkeypatch.setattr("code_execution.lima_backend.subprocess.run", fake_run)

    result = backend.run_cell("pass")

    assert result["success"] is False
    assert result["error"]["type"] == "LimaServiceError"
    assert "invalid JSON" in result["error"]["message"]
    assert "systemd-run stdout:\nnot-json" in result["error"]["traceback"]
    assert result["stderr"] == "service failed"


def test_empty_vm_output_is_reported_as_a_service_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, _, _, _ = _backend(tmp_path)

    def fake_run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")

    monkeypatch.setattr("code_execution.lima_backend.subprocess.run", fake_run)

    result = backend.run_cell("pass")

    assert result["success"] is False
    assert result["error"]["type"] == "LimaServiceError"
    assert "no JSON output" in result["error"]["message"]
    assert "systemd-run exit code: 0" in result["error"]["traceback"]


def test_result_file_recovers_a_dropped_vm_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, _, work, _ = _backend(tmp_path)
    execution_id = "result-file-fallback"
    response = {
        "stdout": "recovered\n",
        "stderr": "",
        "rich_outputs": [],
        "success": True,
        "error": None,
    }

    class FixedUuid:
        hex = execution_id

    def fake_run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "systemd-run" in arguments:
            result_path = work / "thread_1" / ".runtime-cache" / f"{execution_id}.json"
            result_path.parent.mkdir(exist_ok=True)
            result_path.write_text(json.dumps(response), encoding="utf-8")
        return subprocess.CompletedProcess(arguments, 0, stdout="", stderr="")

    monkeypatch.setattr("code_execution.lima_backend.uuid.uuid4", lambda: FixedUuid())
    monkeypatch.setattr("code_execution.lima_backend.subprocess.run", fake_run)

    assert backend.run_cell("print('recovered')") == response
    assert not (work / "thread_1" / ".runtime-cache" / f"{execution_id}.json").exists()


def test_nonzero_vm_exit_includes_service_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend, _, _, _ = _backend(tmp_path)

    def fake_run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if "journalctl" in arguments:
            return subprocess.CompletedProcess(
                arguments,
                0,
                stdout="Failed to set up mount namespacing",
                stderr="",
            )
        return subprocess.CompletedProcess(arguments, 226, stdout="", stderr="namespace failed")

    monkeypatch.setattr("code_execution.lima_backend.subprocess.run", fake_run)

    result = backend.run_cell("pass")

    assert result["success"] is False
    assert result["error"]["type"] == "LimaServiceError"
    assert "exit 226" in result["error"]["message"]
    assert "namespace failed" in result["error"]["traceback"]
    assert "Failed to set up mount namespacing" in result["error"]["traceback"]


def test_lima_integration_reports_missing_runner_result(tmp_path: Path) -> None:
    """A guest exit before JSON serialization must not look like a timeout."""
    lima_path = os.environ.get("AUTODISCOVERY_LIMA_PATH")
    lima_home = os.environ.get("AUTODISCOVERY_LIMA_HOME")
    if not lima_path or not lima_home:
        pytest.skip("requires a configured Lima runtime")

    source = tmp_path / "dataset.csv"
    source.write_text("value\n1\n", encoding="utf-8")
    work = tmp_path / "work" / "thread_integration"
    work.mkdir(parents=True)
    backend = LimaIPythonBackend(
        cwd=str(work),
        dataset_paths=[str(source)],
        lima_path=lima_path,
        lima_home=lima_home,
    )

    result = backend.run_cell("import os; os._exit(0)", timeout_s=60)

    assert result["success"] is False
    assert result["error"]["type"] == "LimaServiceError"
    assert "no JSON output" in result["error"]["message"]
    assert "systemd-run exit code: 0" in result["error"]["traceback"]


def test_unsafe_mount_root_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lima_path = tmp_path / "limactl"
    lima_path.touch()
    source = tmp_path / "source" / "dataset.csv"
    source.parent.mkdir()
    source.touch()
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.setattr(
        "code_execution.lima_backend._FORBIDDEN_MOUNT_ROOTS", {source.parent}
    )

    with pytest.raises(ValueError, match="unsafe VM mount root"):
        LimaIPythonBackend(
            cwd=str(work),
            dataset_paths=[str(source)],
            lima_path=str(lima_path),
            lima_home=str(tmp_path / "lima-home"),
        )


def test_systemd_paths_with_spaces_are_quoted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    spaced_root = tmp_path / "dataset with spaces"
    source = spaced_root / "source data.csv"
    spaced_root.mkdir()
    source.touch()
    work = tmp_path / "work with spaces"
    work.mkdir()
    lima_path = tmp_path / "limactl"
    lima_path.touch()
    backend = LimaIPythonBackend(
        cwd=str(work),
        dataset_paths=[str(source)],
        lima_path=str(lima_path),
        lima_home=str(tmp_path / "lima-home"),
    )
    response = {
        "stdout": "",
        "stderr": "",
        "rich_outputs": [],
        "success": True,
        "error": None,
    }
    calls: list[list[str]] = []

    def fake_run(arguments: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(arguments)
        stdout = json.dumps(response) if "systemd-run" in arguments else ""
        return subprocess.CompletedProcess(arguments, 0, stdout=stdout, stderr="")

    monkeypatch.setattr("code_execution.lima_backend.subprocess.run", fake_run)

    assert backend.run_cell("pass")["success"] is True
    service = next(arguments for arguments in calls if "systemd-run" in arguments)
    assert f"InaccessiblePaths={json.dumps(str(spaced_root))}" in service
    assert f"BindPaths={json.dumps(str(work))}:" in " ".join(service)
    assert f"BindReadOnlyPaths={json.dumps(str(source))}:" in " ".join(service)
