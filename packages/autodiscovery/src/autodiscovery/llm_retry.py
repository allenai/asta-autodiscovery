"""Retry helpers for LLM calls."""

from __future__ import annotations

from dataclasses import dataclass
import functools
import os
from typing import Callable, TypeVar

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
    """Return True when an exception looks like an LLM rate-limit (HTTP 429) error.

    Args:
        exc: The exception to inspect.

    Returns:
        True when the error indicates a rate limit, otherwise False.
    """
    if _is_google_rate_limit_error(exc):
        return True
    if _is_openai_rate_limit_error(exc):
        return True
    if _is_requests_rate_limit_error(exc):
        return True
    status_code = getattr(exc, "status_code", None) or getattr(exc, "http_status", None)
    if status_code == 429:
        return True
    message = str(exc).lower()
    return "429" in message and (
        "resource exhausted" in message or "too many requests" in message or "rate limit" in message
    )


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


def apply_gemini_client_backoff(retry_config: RetryConfig | None = None) -> bool:
    """Wrap Autogen's Gemini client with backoff logic to handle 429 errors.

    Args:
        retry_config: Optional override for retry configuration.

    Returns:
        True if the patch is applied or already active, otherwise False.
    """
    try:
        from autogen.oai.gemini import GeminiClient
    except Exception:
        return False

    if getattr(GeminiClient.create, "_autodiscovery_backoff_wrapped", False):
        return True

    original_create = GeminiClient.create

    @functools.wraps(original_create)
    def wrapped(self, params):
        return call_with_backoff(
            lambda: original_create(self, params),
            label="GeminiClient.create",
            retry_config=retry_config,
        )

    wrapped._autodiscovery_backoff_wrapped = True  # type: ignore[attr-defined]
    GeminiClient.create = wrapped
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


def _is_google_rate_limit_error(exc: Exception) -> bool:
    try:
        from google.api_core import exceptions as google_exceptions
    except Exception:
        return False

    rate_limit_errors = tuple(
        error
        for error in (
            getattr(google_exceptions, "ResourceExhausted", None),
            getattr(google_exceptions, "TooManyRequests", None),
        )
        if error is not None
    )
    return isinstance(exc, rate_limit_errors)


def _is_openai_rate_limit_error(exc: Exception) -> bool:
    try:
        from openai import APIStatusError, RateLimitError
    except Exception:
        return False

    if isinstance(exc, RateLimitError):
        return True
    if isinstance(exc, APIStatusError) and getattr(exc, "status_code", None) == 429:
        return True
    return False


def _is_requests_rate_limit_error(exc: Exception) -> bool:
    try:
        from requests import HTTPError
    except Exception:
        return False

    if isinstance(exc, HTTPError):
        response = getattr(exc, "response", None)
        return getattr(response, "status_code", None) == 429
    return False
