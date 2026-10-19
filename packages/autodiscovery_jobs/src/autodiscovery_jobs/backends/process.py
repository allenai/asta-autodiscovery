"""Host-process job backend.

Launches AutoDiscovery jobs as plain subprocesses of the API, on the API's own
host, with no container runtime. The launched job runs the same engine entry
point (``python -m autodiscovery.run``) with the same CLI arguments as the
container backends — only the process launcher differs.

There is no mount: the job reads and writes the run's directory in the local
store directly, so this backend requires ``STORAGE_BACKEND=local`` (enforced at
startup by ``JobManager``). Its arguments therefore name the store's own root
where the container backends name :data:`~.base.JOB_MOUNT_ROOT`; the paths below
that root are the same store-shaped keys.

Nothing scopes what the job can reach: it runs as the API's user, with the API's
environment, and so does generated code under ``CODE_EXECUTION_BACKEND=process``
or ``local``. That suits a single-user deployment on the user's own machine
(``AUTH_PROVIDER=none``), the same trust model as the standalone CLI.

Each execution gets a directory under ``config.process_job_dir`` holding its
state, its combined output log, and the job's working directory. The job's exit
status is written there by the job's own shell wrapper rather than by the API,
so status stays correct when the API restarts mid-run or a different API worker
process answers the status request.
"""

from __future__ import annotations

import fcntl
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import threading
import uuid
from contextlib import contextmanager, suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..exceptions import JobBackendError
from .base import JobBackend, build_job_args

# The engine entry point every job backend runs (the job image's ENTRYPOINT).
_ENGINE_MODULE = "autodiscovery.run"

# Runs the job, then records its exit status beside it. ``exec`` is avoided so
# the shell outlives the job to write the file; the job is in the shell's
# process group, so cancelling the group stops both.
_EXIT_STATUS_WRAPPER = '"$@"; echo $? > "$AUTODISCOVERY_EXIT_STATUS_FILE"'

_STATE_FILE = "state.json"
_LOG_FILE = "job.log"
_EXIT_STATUS_FILE = "exit_status"
_WORK_DIR = "work"


class ProcessBackend(JobBackend):
    """:class:`JobBackend` that launches jobs as subprocesses on the API's host.

    The ``execution_id`` returned by :meth:`run_job` names the execution's
    directory under ``config.process_job_dir`` and is passed back to the other
    methods to inspect / stop / read logs.
    """

    def __init__(self, config) -> None:
        """Locate the executions directory; it is created on the first launch."""
        super().__init__(config)
        self.executions_root = Path(config.process_job_dir).expanduser().resolve()

    def run_job(self, userid: str, jobid: str, **kwargs) -> str:
        """Launch the AD job as a host subprocess and return its execution ID."""
        store_root = Path(self.config.storage_dir).expanduser().resolve()
        args = build_job_args(userid, jobid, self.config, mount_root=str(store_root), **kwargs)
        python = self.config.process_job_python
        if python is None and importlib.util.find_spec("autodiscovery") is None:
            raise JobBackendError(
                "The process job backend runs the engine with this interpreter, which "
                "does not have the autodiscovery package installed. Install it here, or "
                "set PROCESS_JOB_PYTHON to an interpreter that has it."
            )
        command = [python or sys.executable, "-m", _ENGINE_MODULE, *args]

        with self._launch_lock():
            limit = self.config.process_max_concurrent_jobs
            if limit > 0 and self._running_count() >= limit:
                raise JobBackendError(
                    f"{limit} job(s) already running, the most the process job backend "
                    "runs at once (PROCESS_MAX_CONCURRENT_JOBS). Wait for one to finish."
                )

            # Unique, inspectable name used as the execution_id, as with docker.
            execution_id = f"{self.config.job_name}-{uuid.uuid4().hex[:8]}"
            execution_dir = self.executions_root / execution_id
            work_dir = execution_dir / _WORK_DIR
            work_dir.mkdir(parents=True)
            environment = {
                **os.environ,
                "AUTODISCOVERY_EXIT_STATUS_FILE": str(execution_dir / _EXIT_STATUS_FILE),
            }

            with (execution_dir / _LOG_FILE).open("a", encoding="utf-8") as log_file:
                try:
                    process = subprocess.Popen(
                        ["/bin/sh", "-c", _EXIT_STATUS_WRAPPER, "sh", *command],
                        cwd=work_dir,
                        env=environment,
                        stdin=subprocess.DEVNULL,
                        stdout=log_file,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
                except OSError as e:
                    raise JobBackendError(f"Failed to launch job process: {e}") from e

            self._write_state(
                execution_id,
                {
                    "execution_id": execution_id,
                    "userid": userid,
                    "jobid": jobid,
                    "pid": process.pid,
                    "command": command,
                    "create_time": _now(),
                    "cancel_time": None,
                },
            )

        # Reap the child when it exits so it never lingers as a zombie, which
        # would look alive to _pid_is_running. The exit status itself comes from
        # the wrapper's file, not from here.
        threading.Thread(
            target=process.wait, name=f"autodiscovery-{execution_id}", daemon=True
        ).start()
        return execution_id

    def get_job_status(self, execution_id: str) -> dict[str, Any]:
        """Return status info for the execution, mapped to shared phases."""
        state = self._read_state(execution_id)
        exit_code = self._read_exit_code(execution_id)

        if state.get("cancel_time"):
            phase = "CANCELLED"
        elif exit_code is not None:
            phase = "SUCCEEDED" if exit_code == 0 else "FAILED"
        elif _pid_is_running(int(state["pid"])):
            phase = "RUNNING"
        else:
            # Gone without recording an exit status: killed from outside, or the
            # host restarted.
            phase = "FAILED"

        completion_time = state.get("cancel_time")
        if completion_time is None and phase != "RUNNING":
            completion_time = self._completion_time(execution_id)

        return {
            "name": execution_id,
            "phase": phase,
            "create_time": state.get("create_time"),
            "start_time": state.get("create_time"),
            "completion_time": completion_time,
            "exit_code": exit_code,
        }

    def cancel_job(self, execution_id: str) -> None:
        """Stop the execution's process group."""
        state = self._read_state(execution_id)
        if state.get("cancel_time") or self._read_exit_code(execution_id) is not None:
            return
        with suppress(ProcessLookupError):
            os.killpg(int(state["pid"]), signal.SIGTERM)
        state["cancel_time"] = _now()
        self._write_state(execution_id, state)

    def get_job_logs(self, execution_id: str | None = None, limit: int = 50) -> list[str]:
        """Return recent log lines from the execution's combined output."""
        if not execution_id:
            # Like docker, logs are per execution; there is nothing to return
            # without a specific one.
            return []
        log_path = self._execution_dir(execution_id) / _LOG_FILE
        if not log_path.is_file():
            return []
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        return [line for line in lines if line][-limit:]

    # Execution directory bookkeeping

    def _execution_dir(self, execution_id: str) -> Path:
        """Return an execution's directory, rejecting IDs that are not one path segment."""
        if (
            not execution_id
            or execution_id in {".", ".."}
            or Path(execution_id).name != execution_id
        ):
            raise JobBackendError(f"Invalid execution ID {execution_id!r}")
        return self.executions_root / execution_id

    def _read_state(self, execution_id: str) -> dict[str, Any]:
        state_path = self._execution_dir(execution_id) / _STATE_FILE
        try:
            return json.loads(state_path.read_text(encoding="utf-8"))
        except FileNotFoundError as e:
            raise JobBackendError(f"Job process '{execution_id}' not found") from e

    def _write_state(self, execution_id: str, state: dict[str, Any]) -> None:
        """Atomically replace an execution's state file."""
        execution_dir = self._execution_dir(execution_id)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=execution_dir, suffix=".tmp", delete=False
        ) as temp_file:
            json.dump(state, temp_file, indent=2)
        Path(temp_file.name).replace(execution_dir / _STATE_FILE)

    def _read_exit_code(self, execution_id: str) -> int | None:
        exit_path = self._execution_dir(execution_id) / _EXIT_STATUS_FILE
        try:
            return int(exit_path.read_text(encoding="utf-8").strip())
        except (FileNotFoundError, ValueError):
            # Absent until the job exits; empty for the instant it is being written.
            return None

    def _completion_time(self, execution_id: str) -> str | None:
        exit_path = self._execution_dir(execution_id) / _EXIT_STATUS_FILE
        with suppress(FileNotFoundError):
            return datetime.fromtimestamp(exit_path.stat().st_mtime, UTC).isoformat()
        return None

    def _running_count(self) -> int:
        if not self.executions_root.is_dir():
            return 0
        return sum(
            1
            for execution_dir in self.executions_root.iterdir()
            if (execution_dir / _STATE_FILE).is_file()
            and self.get_job_status(execution_dir.name)["phase"] == "RUNNING"
        )

    @contextmanager
    def _launch_lock(self):
        """Serialize launches across API worker processes, so the limit holds."""
        self.executions_root.mkdir(parents=True, exist_ok=True)
        with (self.executions_root / ".launch.lock").open("w") as lock_file:
            fcntl.flock(lock_file, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _now() -> str:
    return datetime.now(UTC).isoformat()
