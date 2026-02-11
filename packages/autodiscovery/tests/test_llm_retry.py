import http.client
import sys
import types

import pytest
import requests
from autodiscovery import llm_retry
from urllib3.exceptions import ProtocolError


class FakeStatusError(Exception):
    def __init__(self, status_code: int, message: str = ""):
        super().__init__(message)
        self.status_code = status_code


class FakeRetryAfterError(Exception):
    def __init__(self, retry_after: str | float):
        super().__init__("rate limit")
        self.response = type("Resp", (), {"headers": {"Retry-After": str(retry_after)}})()


def test_should_retry_llm_error_status_codes():
    assert llm_retry.should_retry_llm_error(FakeStatusError(429))
    assert llm_retry.should_retry_llm_error(FakeStatusError(503))
    assert not llm_retry.should_retry_llm_error(FakeStatusError(400))


def test_should_retry_llm_error_timeout_message():
    assert llm_retry.should_retry_llm_error(Exception("request timed out"))


def test_should_retry_llm_error_requests_connection_error():
    assert llm_retry.should_retry_llm_error(requests.ConnectionError("connection aborted"))


def test_should_retry_llm_error_urllib3_protocol_error():
    protocol_error = ProtocolError(
        "Connection aborted.",
        http.client.RemoteDisconnected("Remote end closed connection without response"),
    )
    assert llm_retry.should_retry_llm_error(protocol_error)


def test_call_with_backoff_retries_on_retryable():
    attempts = {"count": 0}

    def call():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise FakeStatusError(429)
        return "ok"

    config = llm_retry.RetryConfig(max_retries=3, initial_delay_seconds=0.0, max_delay_seconds=0.0)
    assert llm_retry.call_with_backoff(call, retry_config=config) == "ok"
    assert attempts["count"] == 3


def test_call_with_backoff_does_not_retry_non_retryable():
    attempts = {"count": 0}

    def call():
        attempts["count"] += 1
        raise ValueError("boom")

    config = llm_retry.RetryConfig(max_retries=3, initial_delay_seconds=0.0, max_delay_seconds=0.0)
    with pytest.raises(ValueError):
        llm_retry.call_with_backoff(call, retry_config=config)
    assert attempts["count"] == 1


def test_call_with_backoff_retries_on_connection_error():
    attempts = {"count": 0}

    def call():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise requests.ConnectionError("connection dropped")
        return "ok"

    config = llm_retry.RetryConfig(max_retries=3, initial_delay_seconds=0.0, max_delay_seconds=0.0)
    assert llm_retry.call_with_backoff(call, retry_config=config) == "ok"
    assert attempts["count"] == 3


def test_extract_retry_after_seconds_from_header():
    exc = FakeRetryAfterError("7")
    assert llm_retry._extract_retry_after_seconds(exc) == 7.0


class _DummyOpenAIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.api_key = "stale-token"


class _DummyAG2OpenAIClient:
    def __init__(self, base_url: str):
        self._oai_client = _DummyOpenAIClient(base_url=base_url)

    def create(self, params: dict):
        _ = params
        return self._oai_client.api_key


class _DummyOpenAIWrapper:
    def create(self, **config):
        _ = config
        return {
            "model": "google/gemini-3-flash-preview",
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        }


def test_refresh_vertex_openai_api_key_if_needed(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "autodiscovery.utils.get_vertex_access_token",
        lambda: "fresh-token",
    )
    client = _DummyAG2OpenAIClient(
        base_url="https://aiplatform.googleapis.com/v1/projects/p/locations/global/endpoints/openapi"
    )

    refreshed = llm_retry._refresh_vertex_openai_api_key_if_needed(
        client,
        {"model": "google/gemini-3-flash-preview"},
    )

    assert refreshed is True
    assert client._oai_client.api_key == "fresh-token"


def test_refresh_vertex_openai_api_key_if_needed_skips_non_gemini(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        "autodiscovery.utils.get_vertex_access_token",
        lambda: "fresh-token",
    )
    client = _DummyAG2OpenAIClient(
        base_url="https://aiplatform.googleapis.com/v1/projects/p/locations/global/endpoints/openapi"
    )

    refreshed = llm_retry._refresh_vertex_openai_api_key_if_needed(
        client,
        {"model": "gpt-4o"},
    )

    assert refreshed is False
    assert client._oai_client.api_key == "stale-token"


def test_apply_openai_client_vertex_token_refresh_wraps_create(
    monkeypatch: pytest.MonkeyPatch,
):
    fake_module = types.SimpleNamespace(OpenAIClient=_DummyAG2OpenAIClient)
    monkeypatch.setitem(sys.modules, "autogen.oai.client", fake_module)
    monkeypatch.setattr(
        "autodiscovery.utils.get_vertex_access_token",
        lambda: "fresh-token",
    )

    applied = llm_retry.apply_openai_client_vertex_token_refresh()
    assert applied is True

    client = _DummyAG2OpenAIClient(
        base_url="https://aiplatform.googleapis.com/v1/projects/p/locations/global/endpoints/openapi"
    )
    result = client.create({"model": "google/gemini-3-flash-preview"})
    assert result == "fresh-token"


def test_extract_openai_wrapper_config_prefers_kwargs() -> None:
    extracted = llm_retry._extract_openai_wrapper_config(({"a": 1},), {"b": 2})
    assert extracted == {"a": 1, "b": 2}


def test_apply_openai_wrapper_usage_tracking_records_response(monkeypatch: pytest.MonkeyPatch):
    fake_module = types.SimpleNamespace(OpenAIWrapper=_DummyOpenAIWrapper)
    monkeypatch.setitem(sys.modules, "autogen.oai.client", fake_module)
    captured = {}

    def _capture(response, *, agent_name=None):
        captured["response"] = response
        captured["agent_name"] = agent_name
        return {"ok": True}

    monkeypatch.setattr("autodiscovery.llm_usage.record_ag2_response_usage", _capture)

    applied = llm_retry.apply_openai_wrapper_usage_tracking()
    assert applied is True

    wrapper = _DummyOpenAIWrapper()
    result = wrapper.create(agent=types.SimpleNamespace(name="experiment_generator"))
    assert result["usage"]["total_tokens"] == 12
    assert captured["agent_name"] == "experiment_generator"
    assert captured["response"]["usage"]["total_tokens"] == 12
