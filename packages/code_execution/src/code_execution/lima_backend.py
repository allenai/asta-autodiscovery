"""Virtualization.framework-backed IPython execution through Lima."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import uuid
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .ipython_session import ExecutionConfig
from .process_backend import _SANDBOX_RUNNER

_VM_LOCK = threading.Lock()
_FORBIDDEN_MOUNT_ROOTS = {
    Path("/"),
    Path("/Users"),
    Path("/Volumes"),
    Path.home().resolve(),
}


class LimaIPythonBackend:
    """Execute generated code in a VZ Linux VM with narrowly scoped host shares."""

    def __init__(
        self,
        *,
        cwd: str,
        dataset_paths: list[str],
        lima_path: str | None = None,
        lima_home: str | None = None,
        instance_name: str = "ad",
        guest_python: str = "/opt/autodiscovery-venv/bin/python",
    ) -> None:
        """Configure one backend for a run work directory and approved datasets."""
        self._cwd = Path(cwd).resolve()
        self._dataset_paths = [Path(path).resolve() for path in dataset_paths]
        resolved_lima_path = (
            lima_path
            or os.environ.get("AUTODISCOVERY_LIMA_PATH")
            or shutil.which("limactl")
        )
        configured_lima_home = lima_home or os.environ.get("AUTODISCOVERY_LIMA_HOME")
        self._lima_home = Path(configured_lima_home).expanduser() if configured_lima_home else None
        self._instance_name = instance_name
        self._guest_python = guest_python
        if not resolved_lima_path or not Path(resolved_lima_path).is_file():
            raise RuntimeError("The Lima execution backend requires AUTODISCOVERY_LIMA_PATH")
        self._lima_path = resolved_lima_path
        if self._lima_home is None:
            raise RuntimeError("The Lima execution backend requires AUTODISCOVERY_LIMA_HOME")
        if not self._dataset_paths:
            raise ValueError("The Lima execution backend requires at least one dataset path")
        if not self._cwd.is_dir():
            raise ValueError(f"VM work directory does not exist: {self._cwd}")
        missing_datasets = [path for path in self._dataset_paths if not path.is_file()]
        if missing_datasets:
            raise ValueError(f"VM dataset does not exist: {missing_datasets[0]}")
        unsafe_roots = [
            root
            for root in (*self._dataset_roots, self._work_root)
            if root in _FORBIDDEN_MOUNT_ROOTS
        ]
        if unsafe_roots:
            raise ValueError(f"Refusing unsafe VM mount root: {unsafe_roots[0]}")

    @property
    def _work_root(self) -> Path:
        return self._cwd.parent if self._cwd.name.startswith("thread_") else self._cwd

    @property
    def _dataset_roots(self) -> tuple[Path, ...]:
        roots: list[Path] = []
        for path in sorted({path.parent for path in self._dataset_paths}):
            if not any(path.is_relative_to(root) for root in roots):
                roots.append(path)
        return tuple(roots)

    @property
    def _environment(self) -> dict[str, str]:
        assert self._lima_home is not None
        return {**os.environ, "LIMA_HOME": str(self._lima_home)}

    @property
    def _mount_marker(self) -> Path:
        assert self._lima_home is not None
        return self._lima_home / self._instance_name / ".autodiscovery-mounts.json"

    @staticmethod
    def _systemd_path(path: str | Path) -> str:
        return json.dumps(str(path))

    def _service_diagnostics(self, execution_id: str) -> str:
        """Return a bounded journal excerpt for a failed transient service."""
        try:
            journal = self._run_lima(
                [
                    "shell",
                    self._instance_name,
                    "--",
                    "sudo",
                    "journalctl",
                    "--no-pager",
                    "--unit",
                    f"autodiscovery-{execution_id}.service",
                    "--lines",
                    "40",
                    "--output",
                    "cat",
                ],
                check=False,
                timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            return ""

        output = "\n".join(part for part in (journal.stdout, journal.stderr) if part)
        return output[-8_000:]

    def _service_failure_result(
        self,
        *,
        execution_id: str,
        result: subprocess.CompletedProcess[str],
        message: str,
        raw_stdout: str = "",
    ) -> dict[str, Any]:
        """Normalize a systemd-run failure into the code-execution result contract."""
        diagnostics = [f"systemd-run exit code: {result.returncode}"]
        if result.stderr:
            diagnostics.append(f"systemd-run stderr:\n{result.stderr[-8_000:]}")
        journal = self._service_diagnostics(execution_id)
        if journal:
            diagnostics.append(f"systemd journal:\n{journal}")
        if raw_stdout:
            diagnostics.append(f"systemd-run stdout:\n{raw_stdout[-8_000:]}")
        detail = "\n\n".join(diagnostics)
        return {
            "stdout": "",
            "stderr": result.stderr,
            "rich_outputs": [],
            "success": False,
            "error": {
                "type": "LimaServiceError",
                "message": message,
                "traceback": detail,
            },
        }

    def _run_lima(
        self,
        arguments: list[str],
        *,
        input_text: str | None = None,
        check: bool = True,
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self._lima_path, *arguments],
            input=input_text,
            capture_output=True,
            text=True,
            env=self._environment,
            check=check,
            timeout=timeout,
        )

    def _ensure_mounts(self) -> None:
        expected = {
            "dataset_roots": [str(path) for path in self._dataset_roots],
            "work_root": str(self._work_root),
        }
        with _VM_LOCK:
            try:
                current = json.loads(self._mount_marker.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                current = None
            if current == expected:
                status = self._run_lima(
                    ["list", self._instance_name, "--json"], check=False
                )
                normalized_status = status.stdout.replace(" ", "")
                if status.returncode == 0 and '"status":"Running"' in normalized_status:
                    return

            self._run_lima(["stop", self._instance_name], check=False, timeout=120)
            mounts = [str(path) for path in self._dataset_roots]
            mounts.append(f"{self._work_root}:w")
            self._run_lima(
                [
                    "edit",
                    self._instance_name,
                    "--tty=false",
                    f"--mount-only={','.join(mounts)}",
                    "--mount-type=virtiofs",
                ],
                timeout=120,
            )
            self._run_lima(["start", self._instance_name], timeout=300)
            self._mount_marker.parent.mkdir(parents=True, exist_ok=True)
            self._mount_marker.write_text(json.dumps(expected, indent=2), encoding="utf-8")

    def run_cell(
        self,
        code_str: str,
        *,
        use_subprocess: bool = False,
        timeout_s: float | None = None,
        allow_mime: Iterable[str] | None = None,
        matplotlib_backend: str | None = ExecutionConfig.matplotlib_backend,
    ) -> dict[str, Any]:
        """Execute one code cell inside a transient no-network guest service."""
        self._ensure_mounts()
        timeout_s = timeout_s or 30 * 60
        execution_id = uuid.uuid4().hex
        workspace = f"/run/autodiscovery/{execution_id}"
        guest_cwd = f"{workspace}/thread"
        runtime_cache = self._cwd / ".runtime-cache"
        runtime_cache.mkdir(parents=True, exist_ok=True)
        result_file = runtime_cache / f"{execution_id}.json"
        guest_result_file = f"{guest_cwd}/.runtime-cache/{execution_id}.json"

        setup = self._run_lima(
            [
                "shell",
                self._instance_name,
                "--",
                "sudo",
                "mkdir",
                "-p",
                guest_cwd,
            ]
        )
        del setup

        systemd_arguments = [
            "shell",
            self._instance_name,
            "--",
            "sudo",
            "systemd-run",
            "--quiet",
            "--wait",
            "--pipe",
            "--collect",
            "--unit",
            f"autodiscovery-{execution_id}",
            "--property",
            "User=lima",
            "--property",
            "Group=lima",
            "--property",
            "PrivateNetwork=yes",
            "--property",
            "RestrictAddressFamilies=AF_UNIX",
            "--property",
            "NoNewPrivileges=yes",
            "--property",
            "ProtectSystem=strict",
            "--property",
            "ProtectHome=yes",
            "--property",
            "ProtectKernelTunables=yes",
            "--property",
            "ProtectKernelModules=yes",
            "--property",
            "ProtectKernelLogs=yes",
            "--property",
            "ProtectControlGroups=yes",
            "--property",
            "ProtectClock=yes",
            "--property",
            "ProtectHostname=yes",
            "--property",
            f"ReadWritePaths={guest_cwd}",
            "--property",
            "PrivateTmp=yes",
            "--property",
            "RestrictSUIDSGID=yes",
            "--property",
            "LockPersonality=yes",
            "--property",
            "RestrictRealtime=yes",
            "--property",
            "DevicePolicy=closed",
            "--property",
            "UMask=0077",
            "--property",
            "TasksMax=2048",
            "--property",
            "LimitNOFILE=4096",
            "--property",
            "MemorySwapMax=0",
            "--property",
            "MemoryMax=90%",
            "--property",
            "CapabilityBoundingSet=",
            "--property",
            f"RuntimeMaxSec={int(timeout_s)}",
            "--property",
            f"InaccessiblePaths={self._systemd_path(self._work_root)}",
            "--property",
            f"BindPaths={self._systemd_path(self._cwd)}:{self._systemd_path(guest_cwd)}",
            "--property",
            f"WorkingDirectory={guest_cwd}",
            "--setenv",
            f"IPYTHONDIR={guest_cwd}/.runtime-cache/ipython",
            "--setenv",
            f"MPLCONFIGDIR={guest_cwd}/.runtime-cache/matplotlib",
            "--setenv",
            f"XDG_CACHE_HOME={guest_cwd}/.runtime-cache/xdg",
        ]
        for dataset_root in self._dataset_roots:
            systemd_arguments.extend(
                [
                    "--property",
                    f"InaccessiblePaths={self._systemd_path(dataset_root)}",
                ]
            )
        for dataset_path in self._dataset_paths:
            target = f"{workspace}/{dataset_path.name}"
            systemd_arguments.extend(
                [
                    "--property",
                    "BindReadOnlyPaths="
                    f"{self._systemd_path(dataset_path)}:{self._systemd_path(target)}",
                ]
            )
        systemd_arguments.extend([self._guest_python, "-c", _SANDBOX_RUNNER])

        payload = {
            "code_str": code_str,
            "use_subprocess": use_subprocess,
            "timeout_s": None,
            "allow_mime": list(allow_mime) if allow_mime is not None else None,
            "matplotlib_backend": matplotlib_backend,
            "result_path": guest_result_file,
        }
        try:
            result = self._run_lima(
                systemd_arguments,
                input_text=json.dumps(payload),
                check=False,
                timeout=timeout_s + 60,
            )
        except subprocess.TimeoutExpired:
            return {
                "stdout": "",
                "stderr": "",
                "rich_outputs": [],
                "success": False,
                "error": {
                    "type": "TimeoutError",
                    "message": f"VM execution timed out after {timeout_s}s",
                    "traceback": "",
                },
            }
        finally:
            self._run_lima(
                ["shell", self._instance_name, "--", "sudo", "rm", "-rf", workspace],
                check=False,
            )

        stdout = result.stdout or ""
        if not stdout.strip():
            try:
                stdout = result_file.read_text(encoding="utf-8")
            except FileNotFoundError:
                pass
        try:
            result_file.unlink()
        except FileNotFoundError:
            pass
        if not stdout.strip():
            message = (
                "VM execution completed without a structured result. "
                "The guest service returned no JSON output."
            )
            if result.returncode:
                message = f"VM execution service failed before returning a result (exit {result.returncode})."
            return self._service_failure_result(
                execution_id=execution_id,
                result=result,
                message=message,
            )

        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            return self._service_failure_result(
                execution_id=execution_id,
                result=result,
                message="VM execution service returned invalid JSON.",
                raw_stdout=stdout,
            )
        if not isinstance(parsed, dict):
            return self._service_failure_result(
                execution_id=execution_id,
                result=result,
                message="VM execution service returned a non-object JSON result.",
                raw_stdout=stdout,
            )
        if result.returncode:
            return self._service_failure_result(
                execution_id=execution_id,
                result=result,
                message=f"VM execution service exited with code {result.returncode}.",
                raw_stdout=stdout,
            )
        if result.stderr:
            parsed["stderr"] = f"{parsed.get('stderr', '')}{result.stderr}"
        return parsed
