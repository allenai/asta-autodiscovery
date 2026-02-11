"""Retry helpers for LLM calls."""

from __future__ import annotations

import functools
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_random_exponential

T = TypeVar("T")

LLM_RETRY_MAX_RETRIES_ENV = "LLM_RETRY_MAX_RETRIES"
LLM_RETRY_INITIAL_DELAY_ENV = "LLM_RETRY_INITIAL_DELAY_SECONDS"
LLM_RETRY_MAX_DELAY_ENV = "LLM_RETRY_MAX_DELAY_SECONDS"

@dataclass(frozen=True)
class RetryConfig:
    """Configuration for truncated exponential backoff retries.

    Attributes:
        max_retries: Maximum number of retry attempts after the initial request.
        initial_delay_seconds: Initial backoff delay in seconds.
        max_delay_seconds: Maximum backoff delay in seconds.
    """

    max_retries: int
    initial_delay_seconds: float
    max_delay_seconds: float


def load_retry_config() -> RetryConfig:
    """Load retry configuration from environment variables with defaults.

    Returns:
        RetryConfig populated from environment variables or defaults.
    """
    return RetryConfig(
        max_retries=_env_int(LLM_RETRY_MAX_RETRIES_ENV, 5),
        initial_delay_seconds=_env_float(LLM_RETRY_INITIAL_DELAY_ENV, 1.0),
        max_delay_seconds=_env_float(LLM_RETRY_MAX_DELAY_ENV, 20.0),
    )


def should_retry_llm_error(exc: Exception) -> bool:
    """Return True when an exception looks retryable (rate/network/server).

    Args:
        exc: The exception to inspect.

    Returns:
        True when the error indicates a rate limit, otherwise False.
    """
    if _is_google_retryable_error(exc):
        return True
    if _is_openai_retryable_error(exc):
        return True
    if _is_requests_retryable_error(exc):
        return True
    if _is_urllib3_retryable_error(exc):
        return True
    status_code = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    if status_code == 429 or (status_code is not None and status_code >= 500):
        return True
    message = str(exc).lower()
    if "timeout" in message or "timed out" in message:
        return True
    if "429" in message and (
        "resource exhausted" in message or "too many requests" in message or "rate limit" in message
    ):
        return True
    if (
        "connection aborted" in message
        or "remote end closed connection" in message
        or "connection reset" in message
        or "connection refused" in message
    ):
        return True
    return "5xx" in message or "server error" in message


def call_with_backoff(
    func: Callable[[], T],
    *,
    label: str = "LLM request",
    retry_config: RetryConfig | None = None,
) -> T:
    """Call a function with truncated exponential backoff on retryable LLM errors.

    Args:
        func: Zero-argument callable to invoke.
        label: Label used in retry logs.
        retry_config: Optional override for retry configuration.

    Returns:
        The result of the callable if it succeeds.

    Raises:
        Exception: Re-raises the original exception when retries are exhausted.
    """
    config = retry_config or load_retry_config()
    max_retries = max(0, config.max_retries)
    max_attempts = max_retries + 1

    def _wait(retry_state):
        base_wait = wait_random_exponential(
            min=config.initial_delay_seconds, max=config.max_delay_seconds
        )(retry_state)
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        retry_after = _extract_retry_after_seconds(exc) if exc is not None else None
        if retry_after is None:
            return base_wait
        return max(base_wait, retry_after)

    def _before_sleep(retry_state):
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        sleep_for = retry_state.next_action.sleep if retry_state.next_action else 0.0
        attempt = retry_state.attempt_number
        next_attempt = min(attempt + 1, max_attempts)
        exc_name = exc.__class__.__name__ if exc is not None else "Exception"
        print(
            f"[llm_retry] {label} rate limited ({exc_name}). "
            f"Retrying in {sleep_for:.2f}s (attempt {next_attempt}/{max_attempts})."
        )

    retrying = Retrying(
        retry=retry_if_exception(should_retry_llm_error),
        stop=stop_after_attempt(max_retries + 1),
        wait=_wait,
        reraise=True,
        before_sleep=_before_sleep,
    )

    return retrying(func)


def apply_openai_client_vertex_token_refresh() -> bool:
    """Patch AG2 OpenAI client to refresh Vertex tokens for Gemini requests.

    This wrapper targets AG2's ``OpenAIClient.create`` path, which is used when
    Gemini models are routed through Vertex's OpenAI-compatible endpoint.

    Returns:
        True when the patch is active, otherwise False.
    """
    try:
        from autogen.oai.client import OpenAIClient
    except Exception:
        return False

    if getattr(OpenAIClient.create, "_autodiscovery_vertex_refresh_wrapped", False):
        return True

    original_create = OpenAIClient.create

    @functools.wraps(original_create)
    def wrapped(self, params):
        _refresh_vertex_openai_api_key_if_needed(self, params)
        return original_create(self, params)

    wrapped._autodiscovery_vertex_refresh_wrapped = True  # type: ignore[attr-defined]
    OpenAIClient.create = wrapped
    return True


def apply_openai_wrapper_usage_tracking() -> bool:
    """Patch AG2 OpenAI wrapper to emit per-response usage events.

    Returns:
        True when the patch is active, otherwise False.
    """
    try:
        from autogen.oai.client import OpenAIWrapper
    except Exception:
        return False

    if getattr(OpenAIWrapper.create, "_autodiscovery_usage_wrapped", False):
        return True

    original_create = OpenAIWrapper.create

    @functools.wraps(original_create)
    def wrapped(self, *args: Any, **kwargs: Any):
        response = original_create(self, *args, **kwargs)
        config = _extract_openai_wrapper_config(args, kwargs)
        _record_wrapped_openai_response_usage(response, config)
        return response

    wrapped._autodiscovery_usage_wrapped = True  # type: ignore[attr-defined]
    OpenAIWrapper.create = wrapped
    return True


def _record_wrapped_openai_response_usage(response: Any, config: dict[str, Any]) -> None:
    """Record usage from a wrapped AG2 OpenAI wrapper response."""
    from autodiscovery.llm_usage import record_ag2_response_usage

    agent_obj = config.get("agent")
    agent_name = getattr(agent_obj, "name", None)
    record_ag2_response_usage(response, agent_name=agent_name)


def _extract_openai_wrapper_config(args: tuple[Any, ...], kwargs: dict[str, Any]) -> dict[str, Any]:
    """Extract OpenAIWrapper.create config from positional/keyword args."""
    if args and isinstance(args[0], dict):
        merged = dict(args[0])
        merged.update(kwargs)
        return merged
    return dict(kwargs)


def _refresh_vertex_openai_api_key_if_needed(client: object, params: dict) -> bool:
    """Refresh API key for Vertex OpenAI-compatible Gemini calls.

    Args:
        client: AG2 OpenAIClient instance (or duck-typed equivalent).
        params: Request parameters passed to ``OpenAIClient.create``.

    Returns:
        True if a refreshed token was applied, otherwise False.
    """
    model = params.get("model")
    if not isinstance(model, str):
        return False

    # Only refresh for Gemini model calls.
    if not model.split("/")[-1].startswith("gemini"):
        return False

    oai_client = getattr(client, "_oai_client", None)
    if oai_client is None:
        return False
    base_url = str(getattr(oai_client, "base_url", "") or "")
    # Restrict refresh to Vertex OpenAI-compatible endpoints.
    if "/endpoints/openapi" not in base_url and "aiplatform.googleapis.com" not in base_url:
        return False

    # Imported lazily to avoid module-import cycles.
    from autodiscovery.utils import get_vertex_access_token

    refreshed_token = get_vertex_access_token()
    if not refreshed_token:
        return False
    setattr(oai_client, "api_key", refreshed_token)
    return True


def _env_int(name: str, default: int) -> int:
    # Accept invalid env values gracefully and fall back to defaults.
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def _env_float(name: str, default: float) -> float:
    # Accept invalid env values gracefully and fall back to defaults.
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def _extract_retry_after_seconds(exc: Exception) -> float | None:
    retry_after = getattr(exc, "retry_after", None)
    if isinstance(retry_after, (int, float)) and retry_after >= 0:
        return float(retry_after)
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if not headers:
        return None
    retry_after_header = headers.get("Retry-After")
    if retry_after_header is None:
        return None
    try:
        return float(retry_after_header)
    except (TypeError, ValueError):
        return None


def _is_google_retryable_error(exc: Exception) -> bool:
    try:
        from google.api_core import exceptions as google_exceptions
    except Exception:
        return False

    retryable_errors = tuple(
        error
        for error in (
            getattr(google_exceptions, "ResourceExhausted", None),
            getattr(google_exceptions, "TooManyRequests", None),
            getattr(google_exceptions, "ServiceUnavailable", None),
            getattr(google_exceptions, "DeadlineExceeded", None),
            getattr(google_exceptions, "InternalServerError", None),
        )
        if error is not None
    )
    return isinstance(exc, retryable_errors)


def _is_openai_retryable_error(exc: Exception) -> bool:
    try:
        from openai import APIStatusError, APITimeoutError, RateLimitError
    except Exception:
        return False

    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APITimeoutError):
        return True
    if isinstance(exc, APIStatusError) and getattr(exc, "status_code", None) == 429:
        return True
    if isinstance(exc, APIStatusError) and getattr(exc, "status_code", None) in {500, 502, 503, 504}:
        return True
    return False


def _is_requests_retryable_error(exc: Exception) -> bool:
    try:
        from requests import ConnectionError, HTTPError, Timeout
    except Exception:
        return False

    if isinstance(exc, (ConnectionError, Timeout)):
        return True
    if isinstance(exc, HTTPError):
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        return status == 429 or (status is not None and status >= 500)
    return False


def _is_urllib3_retryable_error(exc: Exception) -> bool:
    try:
        from urllib3.exceptions import (
            ConnectTimeoutError,
            NewConnectionError,
            ProtocolError,
            ReadTimeoutError,
        )
    except Exception:
        return False

    return isinstance(exc, (ProtocolError, ReadTimeoutError, ConnectTimeoutError, NewConnectionError))
