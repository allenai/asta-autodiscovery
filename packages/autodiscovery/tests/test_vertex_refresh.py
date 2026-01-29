import os
import sys
import types

import pytest

from autodiscovery.utils import get_openai_client_for_model, is_gemini_model
import autodiscovery.vertex_client as vertex_client


class DummyOpenAI:
    def __init__(self, api_key: str, base_url: str | None = None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self.kwargs = kwargs

    def ping(self):
        return self.api_key


class DummyCompletions:
    def __init__(self, on_create):
        self._on_create = on_create

    def create(self, **kwargs):
        self._on_create(kwargs)
        return types.SimpleNamespace(choices=[], usage=None)


class DummyChat:
    def __init__(self, completions):
        self.completions = completions


class DummyOpenAIWithChat:
    def __init__(self, api_key: str, base_url: str | None = None, **kwargs):
        self.api_key = api_key
        self.base_url = base_url
        self.kwargs = kwargs
        self.last_call = None
        completions = DummyCompletions(self._record_call)
        self.chat = DummyChat(completions)

    def _record_call(self, payload):
        self.last_call = payload


class DummyCreds:
    def __init__(self, token: str):
        self.valid = False
        self.token = None
        self._token = token
        self.refresh_count = 0

    def refresh(self, request):
        _ = request
        self.valid = True
        self.token = self._token
        self.refresh_count += 1


def install_fake_google_auth(monkeypatch: pytest.MonkeyPatch, token: str = "fresh-token") -> None:
    google = types.ModuleType("google")
    auth = types.ModuleType("google.auth")
    transport = types.ModuleType("google.auth.transport")
    requests = types.ModuleType("google.auth.transport.requests")

    holder = {}

    def default(scopes):
        _ = scopes
        creds = DummyCreds(token)
        holder["creds"] = creds
        return creds, "project"

    class Request:
        pass

    auth.default = default
    requests.Request = Request
    transport.requests = requests
    auth.transport = transport
    google.auth = auth

    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.auth", auth)
    monkeypatch.setitem(sys.modules, "google.auth.transport", transport)
    monkeypatch.setitem(sys.modules, "google.auth.transport.requests", requests)
    return holder


def test_is_gemini_model_accepts_google_prefix():
    assert is_gemini_model("gemini-3-flash-preview")
    assert is_gemini_model("google/gemini-3-flash-preview")
    assert not is_gemini_model("gpt-4o")


def test_get_openai_client_for_model_gemini_returns_refresher(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VERTEX_ACCESS_TOKEN", "static-token")
    monkeypatch.setenv("VERTEX_OPENAI_BASE_URL", "https://example.test")
    gemini_client = get_openai_client_for_model("gemini-3-flash-preview")
    fq_client = get_openai_client_for_model("google/gemini-3-flash-preview")
    assert isinstance(gemini_client, vertex_client.VertexOpenAIClientRefresher)
    assert isinstance(fq_client, vertex_client.VertexOpenAIClientRefresher)


def test_vertex_openai_client_refresher_uses_adc(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("VERTEX_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_ACCESS_TOKEN", raising=False)
    holder = install_fake_google_auth(monkeypatch, token="adc-token")
    monkeypatch.setattr(vertex_client, "OpenAI", DummyOpenAI)

    client = vertex_client.VertexOpenAIClientRefresher(base_url="https://example.test")
    assert client.ping() == "adc-token"
    assert holder["creds"].refresh_count == 1


def test_vertex_openai_client_refresher_uses_static_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("VERTEX_ACCESS_TOKEN", "static-token")
    monkeypatch.setattr(vertex_client, "OpenAI", DummyOpenAI)

    client = vertex_client.VertexOpenAIClientRefresher(base_url="https://example.test")
    assert client.ping() == "static-token"


def test_vertex_refreshing_model_client_create_refreshes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("VERTEX_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_ACCESS_TOKEN", raising=False)
    holder = install_fake_google_auth(monkeypatch, token="adc-token")
    monkeypatch.setattr(vertex_client, "OpenAI", DummyOpenAIWithChat)

    client = vertex_client.VertexRefreshingModelClient(
        {"model": "google/gemini-3-flash-preview", "base_url": "https://example.test"}
    )
    client.create({"messages": [{"role": "user", "content": "ping"}]})
    assert client._client.api_key == "adc-token"
    assert client._client.last_call["model"] == "google/gemini-3-flash-preview"
    assert holder["creds"].refresh_count == 1


@pytest.mark.adc
def test_vertex_openai_client_refresher_adc_integration():
    if os.getenv("VERTEX_ACCESS_TOKEN") or os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN"):
        pytest.skip("Static tokens set; skipping ADC integration test.")
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        pytest.skip("GOOGLE_APPLICATION_CREDENTIALS is not set.")
    try:
        import google.auth  # noqa: F401
    except Exception:
        pytest.skip("google-auth is not available.")

    from autodiscovery.utils import get_vertex_openai_base_url, normalize_vertex_model_name

    try:
        base_url = get_vertex_openai_base_url()
    except ValueError:
        pytest.skip("Vertex base URL is not configured.")

    model = os.getenv("VERTEX_TEST_MODEL", "gemini-3-flash-preview")
    client = vertex_client.VertexOpenAIClientRefresher(base_url=base_url)
    response = client.chat.completions.create(
        model=normalize_vertex_model_name(model),
        messages=[{"role": "user", "content": "ping"}],
        max_tokens=8,
    )
    assert response is not None
    assert getattr(response, "choices", None) is not None
