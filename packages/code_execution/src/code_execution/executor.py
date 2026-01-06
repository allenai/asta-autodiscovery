"""Execution backends for running IPython cells."""

from __future__ import annotations

from collections.abc import Iterable
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


class LocalIPythonBackend:
    """Local backend that executes code via IPythonSession."""

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
