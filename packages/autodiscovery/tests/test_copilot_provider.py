"""Unit tests for the optional GitHub Copilot provider."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
from autodiscovery.agents import ModalSandboxExecutor, get_agents
from autodiscovery.beliefs import BeliefTrueFalseCat
from autodiscovery.copilot import doctor
from autodiscovery.copilot_provider import (
    CopilotAG2Client,
    CopilotCompletion,
    CopilotEmbeddingResult,
    CopilotModelRequestHandler,
    CopilotRuntime,
    CopilotUsage,
    _create_result_tool,
)
from autodiscovery.deduplication import get_embedding
from autodiscovery.llm_usage import UsageTracker
from autodiscovery.structured_outputs import ExperimentCode, ImageAnalysis
from autodiscovery.utils import query_llm
from copilot.tools import ToolInvocation


def test_temperature_request_mutation_recomputes_content_length() -> None:
    request = httpx.Request(
        "POST",
        "https://api.githubcopilot.com/v1/messages",
        json={"messages": [], "temperature": 1},
    )

    mutated = CopilotModelRequestHandler._with_temperature(request, 0.2)

    assert json.loads(mutated.content)["temperature"] == 0.2
    assert int(mutated.headers["content-length"]) == len(mutated.content)


class FakeRuntime:
    def __init__(self) -> None:
        self.calls = []

    def complete(self, **kwargs):
        self.calls.append(kwargs)
        return CopilotCompletion(
            content='{"code":"print(4)"}',
            usage=CopilotUsage(model="claude-haiku-4.5", input_tokens=10, output_tokens=4),
        )


def test_ag2_adapter_returns_expected_response_and_usage() -> None:
    runtime = FakeRuntime()
    client = CopilotAG2Client(
        {"model": "claude-haiku-4.5", "response_format": ExperimentCode},
        runtime=runtime,
    )

    response = client.create(
        {
            "messages": [{"role": "user", "content": "Print 4"}],
            "temperature": 1.0,
        }
    )

    assert client.message_retrieval(response) == ['{"code":"print(4)"}']
    assert client.get_usage(response) == {
        "prompt_tokens": 10,
        "completion_tokens": 4,
        "total_tokens": 14,
        "cost": 0.0,
        "model": "claude-haiku-4.5",
    }
    assert runtime.calls[0]["temperature"] == 1.0
    assert runtime.calls[0]["response_format"] is ExperimentCode


def test_query_llm_copilot_samples_and_records_usage(monkeypatch) -> None:
    runtime = FakeRuntime()
    runtime.complete = lambda **kwargs: CopilotCompletion(
        content='{"belief":"uncertain"}',
        usage=CopilotUsage(
            model="claude-haiku-4.5",
            input_tokens=20,
            output_tokens=3,
            reasoning_tokens=2,
        ),
    )
    monkeypatch.setattr(
        "autodiscovery.copilot_provider.get_copilot_runtime",
        lambda: runtime,
    )
    tracker = UsageTracker()

    responses = query_llm(
        [{"role": "user", "content": "Assess a hypothesis"}],
        n_samples=3,
        model="claude-haiku-4.5",
        llm_provider="copilot",
        temperature=1.0,
        response_format=BeliefTrueFalseCat.ResponseFormat,
        usage_tracker=tracker,
        usage_component="belief.test",
    )

    assert responses == [{"belief": "uncertain"}] * 3
    summary = tracker.get_summary()
    assert summary["totals"]["calls"] == 3
    assert summary["totals"]["prompt_tokens"] == 60
    assert summary["totals"]["completion_tokens"] == 9


def test_copilot_vision_uses_blob_attachment_and_records_usage(monkeypatch) -> None:
    calls = []

    class VisionRuntime:
        def complete(self, **kwargs):
            calls.append(kwargs)
            return CopilotCompletion(
                content=ImageAnalysis(
                    plot_type="bar",
                    title="Test",
                    x_axis_label="x",
                    y_axis_label="y",
                    x_axis_range=[0, 1],
                    y_axis_range=[0, 1],
                    data_trends=["flat"],
                    statistical_insights=[],
                    annotations_and_legends=[],
                ).model_dump_json(),
                usage=CopilotUsage(model="claude-haiku-4.5", input_tokens=30, output_tokens=8),
            )

    monkeypatch.setattr(
        "autodiscovery.copilot_provider.get_copilot_runtime",
        lambda: VisionRuntime(),
    )
    tracker = UsageTracker()
    executor = ModalSandboxExecutor(
        backend=None,
        vision_model="claude-haiku-4.5",
        llm_provider="copilot",
        usage_tracker=tracker,
    )

    response = executor._analyze_image("base64-png")

    assert ImageAnalysis.model_validate_json(response).plot_type == "bar"
    assert calls[0]["response_format"] is ImageAnalysis
    assert calls[0]["attachments"] == [
        {
            "type": "blob",
            "data": "base64-png",
            "mimeType": "image/png",
            "displayName": "experiment-plot.png",
        }
    ]
    assert tracker.get_summary()["totals"]["calls"] == 1


def test_copilot_rejects_local_execution_backend(tmp_path) -> None:
    try:
        get_agents(tmp_path, llm_provider="copilot", backend="local")
    except ValueError as exc:
        assert "requires the process or modal backend" in str(exc)
    else:
        raise AssertionError("Expected the local backend to be rejected")


def test_copilot_agents_accept_reasoning_effort(tmp_path) -> None:
    """Construct the exact local worker agent config without a duplicate AG2 entry."""
    agents = get_agents(
        tmp_path,
        model_name="claude-haiku-4.5",
        llm_provider="copilot",
        reasoning_effort="medium",
        backend="process",
    )

    assert agents["experiment_generator"].client._clients


def test_runtime_drops_unsupported_reasoning_effort() -> None:
    """Do not send a default reasoning effort to models that advertise none."""
    runtime = CopilotRuntime.__new__(CopilotRuntime)
    runtime._reasoning_efforts = {"claude-haiku-4.5": set()}

    assert runtime._normalize_reasoning_effort("claude-haiku-4.5", "medium") is None


def test_runtime_uses_standalone_cli_auth_store(monkeypatch, tmp_path) -> None:
    """Use normal CLI auth mode while retaining a configurable provider home."""
    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def start(self):
            return None

        async def list_models(self):
            return []

    monkeypatch.setattr("autodiscovery.copilot_provider.CopilotClient", FakeClient)
    runtime = CopilotRuntime(base_directory=str(tmp_path))

    asyncio.run(runtime._start_async())

    assert captured["mode"] == "copilot-cli"
    assert captured["use_logged_in_user"] is True
    assert captured["base_directory"] == str(tmp_path)


def test_result_tool_uses_pydantic_schema_and_captures_validated_result() -> None:
    """Constrain structured output through the SDK's Pydantic-backed tool schema."""
    tool, captured = _create_result_tool(ExperimentCode)

    assert tool.name == "submit_result"
    assert tool.parameters == ExperimentCode.model_json_schema()

    result = asyncio.run(
        tool.handler(
            ToolInvocation(
                session_id="session",
                tool_call_id="call",
                tool_name="submit_result",
                arguments={"code": "print(1)"},
            )
        )
    )

    assert result.result_type == "success"
    assert captured == [ExperimentCode(code="print(1)")]


def test_result_tool_rejects_invalid_arguments_without_capture() -> None:
    """Reject schema-invalid tool arguments before AutoDiscovery consumes them."""
    tool, captured = _create_result_tool(ExperimentCode)

    result = asyncio.run(
        tool.handler(
            ToolInvocation(
                session_id="session",
                tool_call_id="call",
                tool_name="submit_result",
                arguments={},
            )
        )
    )

    assert result.result_type == "failure"
    assert captured == []


def test_runtime_collects_schema_backed_tool_result_from_session() -> None:
    """Consume one typed tool invocation without parsing assistant text."""
    created = {}

    class FakeSession:
        session_id = "session"

        async def send_and_wait(self, prompt, **kwargs):
            del prompt, kwargs
            await created["tools"][0].handler(
                ToolInvocation(
                    session_id=self.session_id,
                    tool_call_id="call",
                    tool_name="submit_result",
                    arguments={"code": "print(1)"},
                )
            )

        async def disconnect(self):
            return None

    class FakeClient:
        async def create_session(self, **kwargs):
            created.update(kwargs)
            return FakeSession()

    runtime = CopilotRuntime.__new__(CopilotRuntime)
    runtime._client = FakeClient()
    runtime._handler = SimpleNamespace(
        set_temperature=lambda *args: None,
        clear_session=lambda *args: None,
    )

    completion = asyncio.run(
        runtime._complete_async(
            messages=[{"role": "user", "content": "Write code"}],
            model="claude-sonnet-4.6",
            response_format=ExperimentCode,
            temperature=1.0,
            reasoning_effort="medium",
            attachments=None,
            timeout=30,
        )
    )

    assert ExperimentCode.model_validate_json(completion.content).code == "print(1)"
    assert [tool.name for tool in created["tools"]] == ["submit_result"]
    assert created["available_tools"] == ["submit_result"]


def test_runtime_does_not_retry_structured_failure() -> None:
    """Do not duplicate provider calls when a schema-backed completion fails."""
    runtime = CopilotRuntime.__new__(CopilotRuntime)
    runtime._reasoning_efforts = {"claude-haiku-4.5": set()}
    runtime.start = lambda: None
    runtime._complete_async = lambda **kwargs: kwargs
    attempts = []

    def submit(request, *, timeout):
        attempts.append((request, timeout))
        ExperimentCode.model_validate({})

    runtime._submit = submit

    try:
        runtime.complete(
            messages=[{"role": "user", "content": "Write code"}],
            model="claude-haiku-4.5",
            response_format=ExperimentCode,
            reasoning_effort="medium",
        )
    except Exception:
        pass
    else:
        raise AssertionError("Expected schema-backed completion failure")

    assert len(attempts) == 1


def test_copilot_embeddings_use_supported_default_and_dimensions(monkeypatch) -> None:
    calls = []

    class EmbeddingRuntime:
        def embed(self, texts, **kwargs):
            calls.append((texts, kwargs))
            return CopilotEmbeddingResult(
                vectors=[[1.0, 0.0], [0.0, 1.0]],
                model=kwargs["model"],
                dimensions=kwargs["dimensions"],
                prompt_tokens=5,
                total_tokens=5,
            )

    monkeypatch.setattr(
        "autodiscovery.copilot_provider.get_copilot_runtime",
        lambda: EmbeddingRuntime(),
    )
    tracker = UsageTracker()

    vectors = get_embedding(
        ["first", "second"],
        embedding_provider="copilot",
        dimensions=512,
        usage_tracker=tracker,
    )

    assert vectors.tolist() == [[1.0, 0.0], [0.0, 1.0]]
    assert calls == [
        (
            ["first", "second"],
            {"model": "text-embedding-3-small", "dimensions": 512},
        )
    ]
    assert tracker.get_summary()["totals"]["prompt_tokens"] == 5

    get_embedding(
        ["first", "second"],
        model="text-embedding-ada-002",
        embedding_provider="copilot",
        dimensions=1536,
    )
    assert calls[-1][1]["model"] == "text-embedding-ada-002"


def test_doctor_returns_safe_model_catalog(monkeypatch) -> None:
    model = SimpleNamespace(
        id="claude-haiku-4.5",
        name="Claude Haiku 4.5",
        capabilities=SimpleNamespace(supports=SimpleNamespace(vision=True)),
        supported_reasoning_efforts=["low", "medium"],
    )
    monkeypatch.setattr(
        "autodiscovery.copilot_provider.CopilotRuntime",
        lambda: SimpleNamespace(list_models=lambda: [model], close=lambda: None),
    )
    monkeypatch.setattr(
        "autodiscovery.copilot._runtime_info",
        lambda: {"version": "1", "source": "configured"},
    )

    result = doctor()

    assert result["code"] == "READY"
    assert result["account"] == {"authenticated": True, "label": None}
    assert result["models"] == [
        {
            "id": "claude-haiku-4.5",
            "name": "Claude Haiku 4.5",
            "vision": True,
            "reasoning_efforts": ["low", "medium"],
        }
    ]


def test_doctor_classifies_auth_without_leaking_error(monkeypatch) -> None:
    def fail_runtime():
        raise RuntimeError("not authenticated token=secret-value")

    monkeypatch.setattr("autodiscovery.copilot_provider.CopilotRuntime", fail_runtime)
    monkeypatch.setattr(
        "autodiscovery.copilot._runtime_info",
        lambda: {"version": None, "source": "downloaded"},
    )

    result = doctor()

    assert result["code"] == "AUTH_REQUIRED"
    assert result["account"]["authenticated"] is False
    assert "secret-value" not in json.dumps(result)
