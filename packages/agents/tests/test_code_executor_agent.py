"""Tests for the CodeExecutorAgent execution flow."""

from __future__ import annotations

from typing import Any, cast

import pytest
from agents import experiment_agents
from asta_sandbox import ExecutionResult
from google.adk.agents.invocation_context import InvocationContext
from google.adk.sessions import InMemorySessionService


@pytest.mark.asyncio
async def test_code_executor_agent_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs the custom code executor against a local backend."""
    captured: dict[str, Any] = {}

    class DummyExecutor:
        async def run_code(self, code_str: str, timeout_seconds: float | None = None) -> ExecutionResult:
            captured["code"] = code_str
            return ExecutionResult(stdout="hello\n", stderr="", success=True)

        async def start(self) -> None:
            pass

        async def shutdown(self) -> None:
            pass

        async def add_shares(self, *shares) -> None:
            pass

    monkeypatch.setattr(experiment_agents, "InProcessExecutor", DummyExecutor)

    agent = experiment_agents.create_code_executor_agent(backend="local")

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


@pytest.mark.asyncio
@pytest.mark.modal
async def test_code_executor_agent_modal() -> None:
    """Runs the code executor against the deployed Modal app."""
    agent = experiment_agents.create_code_executor_agent(backend="modal")

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="app",
        user_id="user",
        state={"experiment_code": "print('modal')\n1 + 1"},
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
    result = cast(dict[str, Any], event.actions.state_delta)["execution_result_raw"]
    assert result.success is True
    assert "modal" in result.stdout
