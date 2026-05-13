"""Tests for the CodeExecutorAgent execution flow."""

from __future__ import annotations

from typing import Any, cast

import pytest
from agents import experiment_agents
from asta_sandbox import ExecutionResult
from google.adk.agents.invocation_context import InvocationContext
from google.adk.sessions import InMemorySessionService

from conftest import DummyExecutor


@pytest.mark.asyncio
async def test_code_executor_agent_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs the custom code executor against a local backend."""
    captured: dict[str, Any] = {}

    class CapturingExecutor(DummyExecutor):
        async def run_code(self, code_str: str, timeout_seconds: float | None = None) -> ExecutionResult:
            captured["code"] = code_str
            return ExecutionResult(stdout="hello\n", stderr="", success=True)

    monkeypatch.setattr(experiment_agents, "InProcessExecutor", CapturingExecutor)

    agent = experiment_agents.create_code_executor_agent()

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="app",
        user_id="user",
        state={"experiment_code": "print('hi')"},
    )
    ctx = InvocationContext(
        session_service=session_service,
        invocation_id="invocation",
        agent=agent,
        session=session,
    )

    events = [event async for event in agent.run_async(ctx)]
    assert len(events) == 1
    event = events[0]
    assert captured["code"] == "print('hi')"
    state_delta = cast(dict[str, Any], event.actions.state_delta)
    assert state_delta["execution_summary"].startswith("success: True")
    result = state_delta["execution_result_raw"]
    assert result.stdout == "hello\n"

    await session_service.append_event(session=session, event=event)
    assert session.state["execution_summary"].startswith("success: True")
    assert session.state["execution_result_raw"].success is True


