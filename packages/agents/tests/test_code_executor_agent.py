"""Tests for the CodeExecutorAgent execution flow."""

from __future__ import annotations

from typing import Any, cast

import pytest
from agents import experiment_agents
from google.adk.agents.invocation_context import InvocationContext
from google.adk.sessions import InMemorySessionService


@pytest.mark.asyncio
async def test_code_executor_agent_local(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs the custom code executor against a local backend."""
    captured: dict[str, Any] = {}

    class DummyBackend:
        def run_cell(
            self,
            code_str: str,
            *,
            use_subprocess: bool = False,
            timeout_s: float | None = None,
            allow_mime: Any = None,
            matplotlib_backend: str | None = None,
        ) -> dict[str, Any]:
            captured["init"] = {
                "use_subprocess": use_subprocess,
                "timeout_s": timeout_s,
                "allow_mime": allow_mime,
                "matplotlib_backend": matplotlib_backend,
            }
            captured["code"] = code_str
            return {
                "stdout": "hello\n",
                "stderr": "",
                "rich_outputs": [],
                "success": True,
                "error": None,
            }

    monkeypatch.setattr(experiment_agents, "LocalIPythonBackend", DummyBackend)

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
    assert state_delta["execution_result_raw"]["stdout"] == "hello\n"

    await session_service.append_event(session=session, event=event)
    assert session.state["execution_summary"].startswith("success: True")
    assert session.state["execution_result_raw"]["success"] is True
