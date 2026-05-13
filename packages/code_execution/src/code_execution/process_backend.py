"""Subprocess-based IPython execution backend for local isolated runs."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .ipython_session import ExecutionConfig

_DEFAULT_SANDBOX_PACKAGES = [
    "ipython",
    "numpy",
    "pandas",
    "matplotlib",
    "matplotlib-inline",
    "seaborn",
    "scikit-learn",
    "scipy",
    "statsmodels",
]

_SANDBOX_RUNNER = """\
import json
import sys
import traceback

from code_execution.ipython_session import ExecutionConfig, IPythonSession


def _format_error(exc: BaseException) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    }


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        allow_mime = payload.get("allow_mime")
        session = IPythonSession(
            use_subprocess=payload.get("use_subprocess", False),
            timeout_s=payload.get("timeout_s"),
            allow_mime=allow_mime,
            matplotlib_backend=payload.get(
                "matplotlib_backend",
                ExecutionConfig.matplotlib_backend,
            ),
        )
        result = session.run_cell(payload["code_str"])
    except BaseException as exc:
        result = {
            "stdout": "",
            "stderr": "",
            "rich_outputs": [],
            "success": False,
            "error": _format_error(exc),
        }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
"""


def _find_uv() -> str:
    """Return path to the ``uv`` binary, or raise if not found."""
    uv = shutil.which("uv")
    if uv is None:
        raise RuntimeError(
            "uv is required for ProcessIPythonBackend but was not found on PATH"
        )
    return uv


# TODO: Transplant this implementation onto asta_sandbox.SandboxBase (making run_cell
# async via asyncio.to_thread) and move it into the asta-sandbox library as a first-class
# local process backend alongside InProcessExecutor and ModalEphemeralExecutor. Once done,
# _ProcessBackendAdapter in agents.py can be removed and ProcessIPythonBackend can be used
# directly wherever a SandboxBase is expected.
class ProcessIPythonBackend:
    """Backend that executes IPython cells in isolated subprocesses.

    Each backend instance lazily creates a *base sandbox venv* with a curated
    set of packages (mirroring the Modal sandbox image).  Individual
    ``run_cell`` invocations get a per-process temporary directory so that any
    ``uv pip install`` executed by experiment code does **not** mutate the
    base venv.
    """

    def __init__(
        self,
        *,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        packages: list[str] | None = None,
        sandbox_venv_path: str | None = None,
    ) -> None:
        """Initialize the backend with optional working directory and env vars."""
        self._cwd = cwd
        self._env = env
        self._packages = packages if packages is not None else list(_DEFAULT_SANDBOX_PACKAGES)
        self._sandbox_venv_path: Path | None = (
            Path(sandbox_venv_path) if sandbox_venv_path else None
        )
        self._sandbox_ready = False
        self._owned_venv_dir: tempfile.TemporaryDirectory[str] | None = None

    # -- lazy venv setup -----------------------------------------------------

    def _ensure_sandbox(self) -> Path:
        """Create the base sandbox venv if it doesn't already exist."""
        if self._sandbox_ready and self._sandbox_venv_path is not None:
            return self._sandbox_venv_path

        uv = _find_uv()

        if self._sandbox_venv_path is None:
            self._owned_venv_dir = tempfile.TemporaryDirectory(prefix="process_sandbox_")
            self._sandbox_venv_path = Path(self._owned_venv_dir.name)

        venv_path = self._sandbox_venv_path
        python_bin = venv_path / "bin" / "python"

        if not python_bin.exists():
            subprocess.run(
                [uv, "venv", str(venv_path), "--seed", "--python", sys.executable],
                check=True,
                capture_output=True,
                text=True,
            )

        # Install curated packages
        if self._packages:
            subprocess.run(
                [uv, "pip", "install", "--python", str(python_bin), *self._packages],
                check=True,
                capture_output=True,
                text=True,
            )

        # Install code_execution package (editable) so the sandbox runner works
        code_exec_pkg = Path(__file__).resolve().parent.parent.parent  # packages/code_execution
        subprocess.run(
            [uv, "pip", "install", "--python", str(python_bin), "-e", str(code_exec_pkg)],
            check=True,
            capture_output=True,
            text=True,
        )

        self._sandbox_ready = True
        return venv_path

    @property
    def sandbox_python(self) -> str:
        """Return the path to the sandbox venv's Python interpreter."""
        venv = self._ensure_sandbox()
        return str(venv / "bin" / "python")

    # -- cell execution ------------------------------------------------------

    def run_cell(
        self,
        code_str: str,
        *,
        use_subprocess: bool = False,
        timeout_s: float | None = None,
        allow_mime: Iterable[str] | None = None,
        matplotlib_backend: str | None = ExecutionConfig.matplotlib_backend,
    ) -> dict[str, Any]:
        """Execute a code cell in an isolated subprocess and return normalized outputs."""
        venv_path = self._ensure_sandbox()
        python_bin = str(venv_path / "bin" / "python")

        payload = {
            "code_str": code_str,
            "use_subprocess": use_subprocess,
            "timeout_s": None,
            "allow_mime": list(allow_mime) if allow_mime else None,
            "matplotlib_backend": matplotlib_backend,
        }

        child_env = os.environ.copy()
        if self._env:
            child_env.update(self._env)

        # Per-cell temp directory for any packages installed by experiment code.
        # An `install-package` script on PATH installs into this directory
        # via `uv pip install --target`, keeping the base sandbox venv clean.
        cell_tmp = tempfile.mkdtemp(prefix="cell_pkgs_")
        try:
            cell_install_dir = os.path.join(cell_tmp, "lib")
            os.makedirs(cell_install_dir, exist_ok=True)

            existing_pp = child_env.get("PYTHONPATH", "")
            child_env["PYTHONPATH"] = (
                f"{cell_install_dir}:{existing_pp}" if existing_pp else cell_install_dir
            )

            # Create an install-package script that experiment code calls
            # to install packages into the per-process temp directory.
            script_dir = os.path.join(cell_tmp, "bin")
            os.makedirs(script_dir, exist_ok=True)
            real_uv = _find_uv()
            script_path = os.path.join(script_dir, "install-package")
            with open(script_path, "w") as f:
                f.write(f"""#!/bin/sh
# Install a Python package into the per-process temp directory.
exec "{real_uv}" pip install --target "{cell_install_dir}" --quiet "$@"
""")
            os.chmod(script_path, 0o755)

            venv_bin = str(venv_path / "bin")
            child_env["PATH"] = f"{script_dir}:{venv_bin}:{child_env.get('PATH', '')}"
            child_env["VIRTUAL_ENV"] = str(venv_path)

            try:
                proc = subprocess.run(
                    [python_bin, "-c", _SANDBOX_RUNNER],
                    input=json.dumps(payload),
                    capture_output=True,
                    text=True,
                    timeout=timeout_s,
                    cwd=self._cwd,
                    env=child_env,
                )
            except subprocess.TimeoutExpired:
                return {
                    "stdout": "",
                    "stderr": "",
                    "rich_outputs": [],
                    "success": False,
                    "error": {
                        "type": "TimeoutError",
                        "message": f"Process execution timed out after {timeout_s}s",
                        "traceback": "",
                    },
                }
        finally:
            shutil.rmtree(cell_tmp, ignore_errors=True)

        stdout = proc.stdout or ""
        stderr = proc.stderr or ""

        try:
            result = json.loads(stdout) if stdout.strip() else {}
        except json.JSONDecodeError:
            return {
                "stdout": "",
                "stderr": stderr,
                "rich_outputs": [],
                "success": False,
                "error": {
                    "type": "RuntimeError",
                    "message": "Subprocess output was not valid JSON.",
                    "traceback": stdout,
                },
            }

        if stderr:
            result.setdefault("stderr", "")
            result["stderr"] = f"{result['stderr']}{stderr}"
        return result
