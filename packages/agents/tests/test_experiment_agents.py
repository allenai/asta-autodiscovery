"""Tests for experiment agent helpers and workflow orchestration."""

from __future__ import annotations

import json
from typing import Any

import pytest
from agents import experiment_agents
from agents.structured_outputs import ExperimentAnalyst, ExperimentCode
from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.run_config import RunConfig
from google.adk.models.lite_llm import LiteLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.sessions import InMemorySessionService
from google.genai import types


def _make_llm_response(payload: dict[str, Any]) -> LlmResponse:
    """Create an LLM response carrying JSON payload text."""
    return LlmResponse(
        content=types.Content(
            role="model",
            parts=[types.Part(text=json.dumps(payload))],
        )
    )


def _configure_llm_agent(
    agent: LlmAgent,
    *,
    payload: dict[str, Any],
) -> None:
    """Configure callbacks to return a fixed model response."""

    def before_model_callback(  # type: ignore[no-untyped-def]
        callback_context, llm_request
    ) -> LlmResponse:
        return _make_llm_response(payload)

    agent.before_model_callback = before_model_callback


def _make_workflow_agent(
    *,
    max_programmer_attempts: int = 3,
    model: LiteLlm | None = None,
    analyst_success: bool = True,
    reviewer_success: bool = True,
) -> experiment_agents.ExperimentWorkflowAgent:
    """Create a workflow agent using real LLM agents with mocked callbacks."""
    resolved_model = model or LiteLlm(model="openai/test-model")
    agents = experiment_agents.create_experiment_agents(model=resolved_model)
    _configure_llm_agent(
        agents["experiment_programmer"],
        payload={"code": "print('hi')"},
    )
    _configure_llm_agent(
        agents["experiment_analyst"],
        payload={"analysis": "ok", "success": analyst_success},
    )
    _configure_llm_agent(
        agents["experiment_reviewer"],
        payload={
            "feedback": "ok" if reviewer_success else "fix",
            "success": reviewer_success,
        },
    )
    _configure_llm_agent(
        agents["experiment_reviser"],
        payload={
            "hypothesis": "h",
            "experiment_plan": {
                "objective": "o",
                "steps": "s",
                "deliverables": "d",
            },
        },
    )
    _configure_llm_agent(
        agents["experiment_generator"],
        payload={
            "experiments": [
                {
                    "hypothesis": "h",
                    "experiment_plan": {
                        "objective": "o",
                        "steps": "s",
                        "deliverables": "d",
                    },
                }
            ]
        },
    )
    code_executor = experiment_agents.create_code_executor_agent()
    code_executor.code_executor.run_cell = (  # type: ignore[method-assign]
        lambda code_str, **_: {
            "stdout": "",
            "stderr": "",
            "rich_outputs": [],
            "success": True,
            "error": None,
        }
    )
    return experiment_agents.ExperimentWorkflowAgent(
        name="workflow",
        experiment_generator=agents["experiment_generator"],
        experiment_programmer=agents["experiment_programmer"],
        experiment_analyst=agents["experiment_analyst"],
        experiment_reviewer=agents["experiment_reviewer"],
        experiment_reviser=agents["experiment_reviser"],
        code_executor=code_executor,
        max_programmer_attempts=max_programmer_attempts,
    )


def test_parse_success_handles_payload_types() -> None:
    """Parse success across structured payload types and fallbacks."""
    workflow = experiment_agents.create_experiment_workflow_agent()
    success_payload = ExperimentAnalyst(analysis="ok", success=True)
    failure_payload = ExperimentAnalyst(analysis="no", success=False)

    assert workflow._parse_success(None, ExperimentAnalyst) is False
    assert workflow._parse_success(success_payload, ExperimentAnalyst) is True
    assert workflow._parse_success(failure_payload, ExperimentAnalyst) is False
    assert workflow._parse_success(success_payload.model_dump(), ExperimentAnalyst) is True
    assert workflow._parse_success(success_payload.model_dump_json(), ExperimentAnalyst) is True
    assert workflow._parse_success("not-json", ExperimentAnalyst) is False


def test_extract_code_handles_payload_types() -> None:
    """Extract code across structured payload types and fallbacks."""
    workflow = experiment_agents.create_experiment_workflow_agent()
    code_payload = ExperimentCode(code="print('ok')")

    assert workflow._extract_code(None) is None
    assert workflow._extract_code(code_payload) == "print('ok')"
    assert workflow._extract_code(code_payload.model_dump()) == "print('ok')"
    assert workflow._extract_code(code_payload.model_dump_json()) == "print('ok')"
    assert workflow._extract_code("not-json") is None


def test_create_code_executor_agent_backend_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Select local vs modal execution backends when building agents."""

    class DummyLocalBackend:
        def __init__(self) -> None:
            self.marker = "local"

        def run_cell(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("should not be called")

    class DummyModalBackend:
        def __init__(self, *, app_name: str) -> None:
            self.app_name = app_name

        def run_cell(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("should not be called")

    monkeypatch.setattr(experiment_agents, "LocalIPythonBackend", DummyLocalBackend)
    monkeypatch.setattr(experiment_agents, "ModalIPythonBackend", DummyModalBackend)

    agent_local = experiment_agents.create_code_executor_agent(backend="local")
    assert isinstance(agent_local, experiment_agents.CodeExecutorAgent)
    assert isinstance(agent_local.code_executor._backend, DummyLocalBackend)

    agent_modal = experiment_agents.create_code_executor_agent(
        backend="modal",
        modal_app_name="unit-test",
    )
    assert isinstance(agent_modal, experiment_agents.CodeExecutorAgent)
    assert isinstance(agent_modal.code_executor._backend, DummyModalBackend)
    assert agent_modal.code_executor._backend.app_name == "unit-test"


def test_create_experiment_agents_model_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Apply default or provided model values across experiment agents."""
    monkeypatch.setattr(experiment_agents, "DEFAULT_MODEL", LiteLlm(model="openai/default-model"))

    default_agents = experiment_agents.create_experiment_agents()
    assert all(agent.model is experiment_agents.DEFAULT_MODEL for agent in default_agents.values())

    custom_model = LiteLlm(model="openai/custom-model")
    custom_agents = experiment_agents.create_experiment_agents(model=custom_model)
    assert all(agent.model is custom_model for agent in custom_agents.values())


@pytest.mark.asyncio
async def test_workflow_stops_after_analysis_success() -> None:
    """Stop retry loop when analysis passes on first attempt."""
    workflow = _make_workflow_agent()

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="app",
        user_id="user",
        state={},
    )
    ctx = InvocationContext(
        session_service=session_service,
        invocation_id="invocation",
        agent=workflow,
        session=session,
        run_config=RunConfig(),
    )

    async for event in workflow.run_async(ctx):
        await session_service.append_event(session=session, event=event)

    programmer_events = [
        event for event in session.events if event.author == "experiment_programmer"
    ]
    analyst_events = [event for event in session.events if event.author == "experiment_analyst"]
    reviewer_events = [event for event in session.events if event.author == "experiment_reviewer"]
    reviser_events = [event for event in session.events if event.author == "experiment_reviser"]
    generator_events = [event for event in session.events if event.author == "experiment_generator"]
    assert len(programmer_events) == 1
    assert len(analyst_events) == 1
    assert len(reviewer_events) == 1
    assert len(reviser_events) == 0
    assert len(generator_events) == 1
    assert ctx.session.state["analysis_passed"] is True
    assert ctx.session.state["review_passed"] is True
    assert ctx.session.state["experiment_code"] == "print('hi')"


@pytest.mark.asyncio
async def test_workflow_retries_until_max_attempts() -> None:
    """Retry programmer and analyst until the max attempt count."""
    workflow = _make_workflow_agent(
        max_programmer_attempts=3,
        analyst_success=False,
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="app",
        user_id="user",
        state={},
    )
    ctx = InvocationContext(
        session_service=session_service,
        invocation_id="invocation",
        agent=workflow,
        session=session,
        run_config=RunConfig(),
    )

    async for event in workflow.run_async(ctx):
        await session_service.append_event(session=session, event=event)

    programmer_events = [
        event for event in session.events if event.author == "experiment_programmer"
    ]
    analyst_events = [event for event in session.events if event.author == "experiment_analyst"]
    reviewer_events = [event for event in session.events if event.author == "experiment_reviewer"]
    assert len(programmer_events) == 3
    assert len(analyst_events) == 3
    assert len(reviewer_events) == 1
    assert ctx.session.state["analysis_passed"] is False
    assert ctx.session.state["review_passed"] is True


@pytest.mark.asyncio
async def test_workflow_revision_flow_after_review_failure() -> None:
    """Run revision and a final programming pass after review failure."""
    workflow = _make_workflow_agent(
        reviewer_success=False,
    )

    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name="app",
        user_id="user",
        state={},
    )
    ctx = InvocationContext(
        session_service=session_service,
        invocation_id="invocation",
        agent=workflow,
        session=session,
        run_config=RunConfig(),
    )

    async for event in workflow.run_async(ctx):
        await session_service.append_event(session=session, event=event)

    programmer_events = [
        event for event in session.events if event.author == "experiment_programmer"
    ]
    analyst_events = [event for event in session.events if event.author == "experiment_analyst"]
    reviewer_events = [event for event in session.events if event.author == "experiment_reviewer"]
    reviser_events = [event for event in session.events if event.author == "experiment_reviser"]
    generator_events = [event for event in session.events if event.author == "experiment_generator"]
    assert len(programmer_events) == 2
    assert len(analyst_events) == 1
    assert len(reviewer_events) == 1
    assert len(reviser_events) == 1
    assert len(generator_events) == 1
