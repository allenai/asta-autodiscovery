"""Shared test fixtures and helpers for the agents package."""

from __future__ import annotations

from asta_sandbox import ExecutionResult


class DummyExecutor:
    """Minimal SandboxExecutor implementation for unit tests.

    Returns an empty successful ExecutionResult by default. Override
    run_code in a subclass to inject test-specific behaviour.
    """

    async def start(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass

    async def run_code(self, code: str, timeout_seconds: float | None = None) -> ExecutionResult:
        return ExecutionResult(stdout="", stderr="", success=True)

    async def add_shares(self, *shares) -> None:
        pass
