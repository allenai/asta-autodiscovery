import http.client

import pytest
import requests
from urllib3.exceptions import ProtocolError

from autodiscovery import llm_retry


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
