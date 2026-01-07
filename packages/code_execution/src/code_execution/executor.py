"""Execution backends for running IPython cells."""

from __future__ import annotations

import os
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any, Protocol

from .ipython_session import ExecutionConfig, IPythonSession


class IPythonBackend(Protocol):
    """Protocol for backends that execute IPython cells."""

    def run_cell(
        self,
        code_str: str,
        *,
        use_subprocess: bool = False,
        timeout_s: float | None = None,
        allow_mime: Iterable[str] | None = None,
        matplotlib_backend: str | None = ExecutionConfig.matplotlib_backend,
    ) -> dict[str, Any]:
        """Execute a code cell and return normalized outputs."""
        ...


@contextmanager
def _execution_context(cwd: str | None, env: dict[str, str] | None) -> Iterable[None]:
    # Temporarily apply environment and working directory changes for a run.
    previous_cwd = os.getcwd()
    previous_env: dict[str, str | None] = {}
    try:
        if env:
            for key, value in env.items():
                previous_env[key] = os.environ.get(key)
                os.environ[key] = value
        if cwd:
            os.chdir(cwd)
        yield
    finally:
        if cwd:
            os.chdir(previous_cwd)
        if env:
            for key in env:
                previous_value = previous_env.get(key)
                if previous_value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = previous_value


class LocalIPythonBackend:
    """Local backend that executes code via IPythonSession."""

    def __init__(self, *, cwd: str | None = None, env: dict[str, str] | None = None) -> None:
        """Initialize the backend with optional working directory and env vars."""
        self._cwd = cwd
        self._env = env

    def run_cell(
        self,
        code_str: str,
        *,
        use_subprocess: bool = False,
        timeout_s: float | None = None,
        allow_mime: Iterable[str] | None = None,
        matplotlib_backend: str | None = ExecutionConfig.matplotlib_backend,
    ) -> dict[str, Any]:
        """Execute a code cell in a local IPython session."""
        with _execution_context(self._cwd, self._env):
            session = IPythonSession(
                use_subprocess=use_subprocess,
                timeout_s=timeout_s,
                allow_mime=allow_mime,
                matplotlib_backend=matplotlib_backend,
            )
            return session.run_cell(code_str)


class IPythonExecutor:
    """Facade that executes IPython cells via a configurable backend."""

    def __init__(self, backend: IPythonBackend) -> None:
        """Initialize the executor with the provided backend."""
        self._backend = backend

    def run_cell(
        self,
        code_str: str,
        *,
        use_subprocess: bool = False,
        timeout_s: float | None = None,
        allow_mime: Iterable[str] | None = None,
        matplotlib_backend: str | None = ExecutionConfig.matplotlib_backend,
    ) -> dict[str, Any]:
        """Execute a code cell using the configured backend."""
        return self._backend.run_cell(
            code_str,
            use_subprocess=use_subprocess,
            timeout_s=timeout_s,
            allow_mime=allow_mime,
            matplotlib_backend=matplotlib_backend,
        )
