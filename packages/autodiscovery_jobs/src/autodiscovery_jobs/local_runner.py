"""Managed subprocess execution for local AutoDiscovery runs."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import threading
import uuid
from collections.abc import Sequence
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import JobConfig


class LocalProcessRunner:
    """Run local jobs in isolated process groups with persistent state and logs."""

    def __init__(self, config: JobConfig) -> None:
        """Initialize the runner for a configured application data root."""
        self.config = config
        self.root = Path(config.local_root).expanduser().resolve()
        self.executions_root = self.root / "executions"
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _now() -> str:
        return datetime.now(UTC).isoformat()

    def _state_path(self, execution_id: str) -> Path:
        if not execution_id.startswith("local-") or Path(execution_id).name != execution_id:
            raise ValueError("Invalid local execution ID")
        return self.executions_root / f"{execution_id}.json"

    def _write_state(self, state: dict[str, Any]) -> None:
        self.executions_root.mkdir(parents=True, exist_ok=True)
        destination = self._state_path(str(state["execution_id"]))
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=self.executions_root,
            prefix=".execution-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            json.dump(state, temp_file, indent=2)
            temp_path = Path(temp_file.name)
        temp_path.replace(destination)

    def _read_state(self, execution_id: str) -> dict[str, Any]:
        state_path = self._state_path(execution_id)
        if not state_path.is_file():
            raise FileNotFoundError(f"Unknown local execution: {execution_id}")
        with state_path.open(encoding="utf-8") as state_file:
            state = json.load(state_file)
        if not isinstance(state, dict):
            raise ValueError("Local execution state must be a JSON object")
        return state

    @staticmethod
    def _pid_is_running(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True

    def _running_count(self) -> int:
        if not self.executions_root.is_dir():
            return 0
        count = 0
        for state_path in self.executions_root.glob("local-*.json"):
            try:
                with state_path.open(encoding="utf-8") as state_file:
                    state = json.load(state_file)
                if state.get("phase") == "RUNNING" and self._pid_is_running(int(state["pid"])):
                    count += 1
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                continue
        return count

    def start(
        self,
        command: Sequence[str],
        *,
        run_id: str,
        cwd: Path,
        log_path: Path,
        env: dict[str, str] | None = None,
    ) -> str:
        """Start one managed command and return its persistent execution ID."""
        if not command:
            raise ValueError("Local execution command may not be empty")
        with self._lock:
            if self._running_count() >= self.config.local_max_concurrent_jobs:
                raise RuntimeError("Local job concurrency limit reached")
            execution_id = f"local-{uuid.uuid4()}"
            cwd.mkdir(parents=True, exist_ok=True)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_file = log_path.open("a", encoding="utf-8")
            try:
                process = subprocess.Popen(
                    list(command),
                    cwd=cwd,
                    env=env,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    text=True,
                    start_new_session=True,
                )
            finally:
                log_file.close()
            state = {
                "execution_id": execution_id,
                "run_id": run_id,
                "pid": process.pid,
                "phase": "RUNNING",
                "command": list(command),
                "cwd": str(cwd),
                "log_path": str(log_path),
                "create_time": self._now(),
                "completion_time": None,
                "return_code": None,
            }
            self._processes[execution_id] = process
            self._write_state(state)
            threading.Thread(
                target=self._monitor,
                args=(execution_id, process),
                name=f"autodiscovery-{execution_id}",
                daemon=True,
            ).start()
            return execution_id

    def _monitor(self, execution_id: str, process: subprocess.Popen[str]) -> None:
        return_code = process.wait()
        with self._lock:
            state = self._read_state(execution_id)
            if state.get("phase") != "CANCELLED":
                state["phase"] = "SUCCEEDED" if return_code == 0 else "FAILED"
            state["return_code"] = return_code
            state["completion_time"] = self._now()
            self._write_state(state)
            self._processes.pop(execution_id, None)

    def get_status(self, execution_id: str) -> dict[str, Any]:
        """Return persisted status, detecting stale running processes after restart."""
        with self._lock:
            state = self._read_state(execution_id)
            if state.get("phase") == "RUNNING" and not self._pid_is_running(int(state["pid"])):
                state["phase"] = "FAILED"
                state["completion_time"] = self._now()
                state["error_code"] = "PROCESS_LOST"
                self._write_state(state)
            return dict(state)

    def cancel(self, execution_id: str) -> None:
        """Terminate an execution process group and persist cancellation."""
        with self._lock:
            state = self._read_state(execution_id)
            if state.get("phase") != "RUNNING":
                return
            pid = int(state["pid"])
            with suppress(ProcessLookupError):
                os.killpg(pid, signal.SIGTERM)
            state["phase"] = "CANCELLED"
            state["completion_time"] = self._now()
            self._write_state(state)

    def get_logs(self, execution_id: str, limit: int = 50) -> list[str]:
        """Return the last requested lines from a local execution log."""
        state = self._read_state(execution_id)
        log_path = Path(str(state["log_path"]))
        if not log_path.is_file():
            return []
        return log_path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
