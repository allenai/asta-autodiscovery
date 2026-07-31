from __future__ import annotations

import json
import subprocess
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
    assert result["error"]["type"] == "RuntimeError"
    assert result["error"]["traceback"] == "not-json"
    assert result["stderr"] == "service failed"


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
