"""GitHub Copilot provider backed by the official Python SDK."""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import json
import os
import threading
from concurrent.futures import Future
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import httpx
from pydantic import BaseModel

try:
    from copilot import CopilotClient, define_tool
    from copilot.copilot_request_handler import CopilotRequestContext, CopilotRequestHandler
    from copilot.session import Attachment, ReasoningEffort
    from copilot.session_events import AssistantUsageData
    from copilot.tools import ToolInvocation
except ImportError as exc:  # pragma: no cover - exercised without the optional extra
    raise ImportError(
        "GitHub Copilot support requires the 'copilot' extra: "
        "pip install 'asta-autodiscovery[copilot]'"
    ) from exc


DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSIONS = 1536


@dataclass(frozen=True)
class CopilotUsage:
    """Token and provider metadata for one Copilot completion."""

    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    provider_cost: float | None = None
    finish_reason: str | None = None

    @property
    def total_tokens(self) -> int:
        """Return input and output tokens combined."""
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class CopilotCompletion:
    """Validated completion content and its usage metadata."""

    content: str
    usage: CopilotUsage


@dataclass(frozen=True)
class CopilotEmbeddingResult:
    """Ordered embedding vectors and provider usage metadata."""

    vectors: list[list[float]]
    model: str
    dimensions: int
    prompt_tokens: int = 0
    total_tokens: int = 0


class CopilotModelRequestHandler(CopilotRequestHandler):
    """Inject per-session model options and expose authenticated embeddings."""

    def __init__(self) -> None:
        """Initialize session options and captured CAPI credentials."""
        self._session_temperatures: dict[str, float] = {}
        self._capi_url: httpx.URL | None = None
        self._capi_headers: dict[str, str] | None = None

    def set_temperature(self, session_id: str, temperature: float | None) -> None:
        """Set the temperature to inject for one Copilot session."""
        if temperature is None:
            self._session_temperatures.pop(session_id, None)
        else:
            self._session_temperatures[session_id] = temperature

    def clear_session(self, session_id: str) -> None:
        """Discard model options associated with a completed session."""
        self._session_temperatures.pop(session_id, None)

    async def send_request(
        self,
        request: httpx.Request,
        ctx: CopilotRequestContext,
    ) -> httpx.Response:
        """Capture CAPI access and inject session-specific model options."""
        self._remember_capi_request(request)
        temperature = self._session_temperatures.get(ctx.session_id or "")
        if temperature is not None:
            request = self._with_temperature(request, temperature)
        return await super().send_request(request, ctx)

    def _remember_capi_request(self, request: httpx.Request) -> None:
        if request.url.path not in {"/models", "/chat/completions", "/responses", "/v1/messages"}:
            return
        self._capi_url = request.url.copy_with(path="/embeddings", query=None)
        self._capi_headers = {
            name: value
            for name, value in request.headers.items()
            if name.lower()
            not in {"content-length", "content-type", "host", "transfer-encoding"}
        }

    @staticmethod
    def _with_temperature(request: httpx.Request, temperature: float) -> httpx.Request:
        if not request.content:
            return request
        try:
            body = json.loads(request.content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return request
        if not isinstance(body, dict) or not ("messages" in body or "input" in body):
            return request
        body["temperature"] = temperature
        headers = {
            name: value
            for name, value in request.headers.items()
            if name.lower() not in {"content-length", "transfer-encoding"}
        }
        return httpx.Request(
            request.method,
            request.url,
            headers=headers,
            content=json.dumps(body).encode("utf-8"),
        )

    async def embed(
        self,
        texts: list[str],
        *,
        model: str,
        dimensions: int | None,
        batch_size: int = 512,
    ) -> CopilotEmbeddingResult:
        """Request ordered embeddings through the authenticated CAPI endpoint."""
        if self._capi_url is None or self._capi_headers is None:
            raise RuntimeError("Copilot embedding endpoint is unavailable before provider startup")
        vectors: list[list[float]] = []
        prompt_tokens = 0
        total_tokens = 0
        async with httpx.AsyncClient(timeout=120) as client:
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                payload: dict[str, Any] = {"input": batch, "model": model}
                if dimensions is not None:
                    payload["dimensions"] = dimensions
                response = await client.post(
                    self._capi_url,
                    headers=self._capi_headers,
                    json=payload,
                )
                parsed = response.json()
                if response.status_code != 200 or not isinstance(parsed, dict):
                    raise RuntimeError(
                        f"Copilot embeddings failed ({response.status_code}): {parsed!r}"
                    )
                data = parsed.get("data")
                if not isinstance(data, list) or len(data) != len(batch):
                    raise RuntimeError("Copilot embeddings returned an unexpected vector count")
                for item in data:
                    vector = item.get("embedding") if isinstance(item, dict) else None
                    if not isinstance(vector, list):
                        raise RuntimeError("Copilot embeddings returned an invalid vector")
                    vectors.append([float(value) for value in vector])
                usage = parsed.get("usage") or {}
                prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
                total_tokens += int(usage.get("total_tokens", 0) or 0)
        actual_dimensions = len(vectors[0]) if vectors else dimensions or 0
        if any(len(vector) != actual_dimensions for vector in vectors):
            raise RuntimeError("Copilot embeddings returned inconsistent dimensions")
        return CopilotEmbeddingResult(
            vectors=vectors,
            model=model,
            dimensions=actual_dimensions,
            prompt_tokens=prompt_tokens,
            total_tokens=total_tokens,
        )


def _create_result_tool(response_format: type[BaseModel]) -> tuple[Any, list[BaseModel]]:
    """Create the only tool exposed to a structured Copilot session."""
    captured: list[BaseModel] = []

    def submit_result(result: BaseModel, invocation: ToolInvocation) -> str:
        del invocation
        captured.append(result)
        return "Structured result accepted. End the response."

    tool = define_tool(
        name="submit_result",
        description="Submit the final structured result for this request.",
        params_type=response_format,
        handler=submit_result,
        skip_permission=True,
        defer="never",
    )
    return tool, captured


class CopilotRuntime:
    """Own one Copilot SDK client and event loop for a process-local run."""

    def __init__(self, *, base_directory: str | None = None) -> None:
        """Initialize a managed event loop and process-local SDK client."""
        self.base_directory = base_directory or os.getenv(
            "AUTODISCOVERY_COPILOT_HOME",
            str(Path.home() / ".copilot"),
        )
        self._loop = asyncio.new_event_loop()
        self._ready = threading.Event()
        self._thread = threading.Thread(target=self._run_loop, name="copilot-runtime", daemon=True)
        self._client: CopilotClient | None = None
        self._handler = CopilotModelRequestHandler()
        self._reasoning_efforts: dict[str, set[str]] = {}
        self._started = False
        self._closed = False

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()

    def _submit(self, coroutine: Any, *, timeout: float | None = None) -> Any:
        if self._closed:
            raise RuntimeError("Copilot runtime is closed")
        if not self._thread.is_alive():
            self._thread.start()
            self._ready.wait()
        future: Future[Any] = asyncio.run_coroutine_threadsafe(coroutine, self._loop)
        return future.result(timeout=timeout)

    def start(self) -> None:
        """Start the SDK client once and prime its authenticated catalog."""
        if self._started:
            return
        self._submit(self._start_async(), timeout=120)
        self._started = True

    async def _start_async(self) -> None:
        Path(self.base_directory).mkdir(parents=True, exist_ok=True)
        self._client = CopilotClient(
            mode="copilot-cli",
            use_logged_in_user=True,
            base_directory=self.base_directory,
            log_level="error",
            request_handler=self._handler,
        )
        await self._client.start()
        models = await self._client.list_models()
        self._reasoning_efforts = {
            model.id: set(model.supported_reasoning_efforts or []) for model in models
        }

    def list_models(self) -> list[Any]:
        """Return models available to the authenticated Copilot account."""
        self.start()
        assert self._client is not None
        return self._submit(self._client.list_models(), timeout=60)

    def _normalize_reasoning_effort(
        self,
        model: str,
        requested: str | None,
    ) -> ReasoningEffort | None:
        if requested not in {"low", "medium", "high", "xhigh"}:
            return None
        supported_efforts = self._reasoning_efforts.get(model)
        if supported_efforts is not None and requested not in supported_efforts:
            return None
        return cast(ReasoningEffort, requested)

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        response_format: type[BaseModel],
        temperature: float | None = None,
        reasoning_effort: str | None = None,
        attachments: list[Attachment] | None = None,
        timeout: float = 600,
    ) -> CopilotCompletion:
        """Run one schema-backed completion in a fresh Copilot session."""
        self.start()
        reasoning_effort = self._normalize_reasoning_effort(model, reasoning_effort)
        return self._submit(
            self._complete_async(
                messages=messages,
                model=model,
                response_format=response_format,
                temperature=temperature,
                reasoning_effort=reasoning_effort,
                attachments=attachments,
                timeout=timeout,
            ),
            timeout=timeout + 30,
        )

    async def _complete_async(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        response_format: type[BaseModel],
        temperature: float | None,
        reasoning_effort: ReasoningEffort | None,
        attachments: list[Attachment] | None,
        timeout: float,  # noqa: ASYNC109 - passed to the SDK request timeout
    ) -> CopilotCompletion:
        assert self._client is not None
        system_parts: list[str] = []
        turn_parts: list[str] = []
        for message in messages:
            content = message.get("content", "")
            text = content if isinstance(content, str) else json.dumps(content)
            if message.get("role") == "system":
                system_parts.append(text)
            else:
                turn_parts.append(f"{str(message.get('role', 'user')).upper()}: {text}")
        usage_events: list[CopilotUsage] = []

        def on_event(event: Any) -> None:
            if isinstance(event.data, AssistantUsageData):
                usage_events.append(
                    CopilotUsage(
                        model=event.data.model,
                        input_tokens=event.data.input_tokens or 0,
                        output_tokens=event.data.output_tokens or 0,
                        reasoning_tokens=event.data.reasoning_tokens or 0,
                        cache_read_tokens=event.data.cache_read_tokens or 0,
                        cache_write_tokens=event.data.cache_write_tokens or 0,
                        provider_cost=event.data.cost,
                        finish_reason=event.data.finish_reason,
                    )
                )

        result_tool, captured_results = _create_result_tool(response_format)

        session = await self._client.create_session(
            model=model,
            reasoning_effort=reasoning_effort,
            system_message={
                "mode": "replace",
                "content": (
                    "\n\n".join(system_parts)
                    + "\n\nYou must finish by calling submit_result exactly once. "
                    "Do not return the result as prose or JSON text."
                ),
            },
            tools=[result_tool],
            available_tools=["submit_result"],
            mcp_servers={},
            capi={"enable_web_socket_responses": False},
            enable_config_discovery=False,
            enable_skills=False,
            skip_custom_instructions=True,
            infinite_sessions={"enabled": False},
            memory={"enabled": False},
            on_event=on_event,
        )
        self._handler.set_temperature(session.session_id, temperature)
        try:
            await session.send_and_wait(
                "\n\n".join(turn_parts) or "Return a valid response.",
                attachments=attachments,
                timeout=timeout,
            )
            if len(captured_results) != 1:
                raise RuntimeError(
                    "Copilot did not submit exactly one schema-backed result "
                    f"(received {len(captured_results)})"
                )
            validated = response_format.model_validate(captured_results[0])
        finally:
            self._handler.clear_session(session.session_id)
            await session.disconnect()
        usage = usage_events[-1] if usage_events else CopilotUsage(model=model)
        return CopilotCompletion(content=validated.model_dump_json(), usage=usage)

    def embed(
        self,
        texts: list[str],
        *,
        model: str = DEFAULT_EMBEDDING_MODEL,
        dimensions: int | None = DEFAULT_EMBEDDING_DIMENSIONS,
    ) -> CopilotEmbeddingResult:
        """Return embeddings from the authenticated Copilot runtime."""
        self.start()
        return self._submit(
            self._handler.embed(texts, model=model, dimensions=dimensions),
            timeout=180,
        )

    def close(self) -> None:
        """Stop the SDK client and its managed event loop."""
        if self._closed:
            return
        if self._client is not None:
            self._submit(self._client.stop(), timeout=30)
        self._closed = True
        if self._thread.is_alive():
            self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=10)


_runtime: CopilotRuntime | None = None
_runtime_lock = threading.Lock()


def get_copilot_runtime() -> CopilotRuntime:
    """Return the process-local managed Copilot runtime."""
    global _runtime
    with _runtime_lock:
        if _runtime is None:
            _runtime = CopilotRuntime()
        return _runtime


def close_copilot_runtime() -> None:
    """Close and discard the process-local Copilot runtime."""
    global _runtime
    with _runtime_lock:
        if _runtime is not None:
            with contextlib.suppress(RuntimeError):
                _runtime.close()
            _runtime = None


atexit.register(close_copilot_runtime)


@dataclass
class AG2Choice:
    """Minimal AG2-compatible completion choice."""

    message: dict[str, str]


@dataclass
class AG2Response:
    """Minimal AG2-compatible completion response."""

    choices: list[AG2Choice]
    model: str
    usage: Any


class CopilotAG2Client:
    """AG2 ModelClient adapter for Copilot structured completions."""

    def __init__(self, config: dict[str, Any], *, runtime: CopilotRuntime | None = None) -> None:
        """Initialize the adapter from an AG2 model configuration."""
        self.config = config
        self.runtime = runtime or get_copilot_runtime()

    def create(self, params: dict[str, Any]) -> AG2Response:
        """Create one AG2-compatible structured Copilot response."""
        response_format = params.get("response_format") or self.config.get("response_format")
        if not isinstance(response_format, type) or not issubclass(response_format, BaseModel):
            raise TypeError(f"Copilot requires a Pydantic response_format, got {response_format!r}")
        model = str(params.get("model") or self.config.get("model"))
        completion = self.runtime.complete(
            messages=params.get("messages") or [],
            model=model,
            response_format=response_format,
            temperature=params.get("temperature"),
            reasoning_effort=params.get("reasoning_effort"),
            timeout=float(params.get("timeout", 600)),
        )
        return AG2Response(
            choices=[AG2Choice(message={"content": completion.content})],
            model=model,
            usage=SimpleNamespace(
                prompt_tokens=completion.usage.input_tokens,
                completion_tokens=completion.usage.output_tokens,
                total_tokens=completion.usage.total_tokens,
            ),
        )

    def message_retrieval(self, response: AG2Response) -> list[str]:
        """Extract assistant message content from an adapter response."""
        return [choice.message["content"] for choice in response.choices]

    def cost(self, response: AG2Response) -> float:
        """Return zero because Copilot's provider cost unit is not monetary."""
        del response
        return 0.0

    @staticmethod
    def get_usage(response: AG2Response) -> dict[str, Any]:
        """Return AG2-compatible token usage metadata."""
        return {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
            "cost": 0.0,
            "model": response.model,
        }
