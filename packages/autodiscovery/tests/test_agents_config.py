"""Tests for the litellm-backed AG2 model client and config."""

from types import SimpleNamespace

import pytest
from autodiscovery.agents import LiteLLMAG2Client, get_llm_config


def test_llm_config_uses_canonical_model_and_one_client_for_every_provider() -> None:
    """Every provider goes through the same AG2 client; only the name differs."""
    for flag, expected in [
        ("gemini-3-flash-preview", "vertex_ai/gemini-3-flash-preview"),
        ("google/gemini-3-flash-preview", "vertex_ai/gemini-3-flash-preview"),
        ("gpt-4o", "openai/gpt-4o"),
        ("github_copilot/claude-haiku-4.5", "github_copilot/claude-haiku-4.5"),
    ]:
        config = get_llm_config(model_name=flag)
        entry = config["config_list"][0]
        assert entry["model"] == expected
        assert entry["model_client_cls"] == "LiteLLMAG2Client"
        assert config["cache_seed"] is None


def test_llm_config_omits_temperature_for_openai_reasoning_models() -> None:
    """OpenAI reasoning models reject temperature; litellm would not drop it."""
    assert "temperature" not in get_llm_config("o4-mini", temperature=0.7)["config_list"][0]
    # Gemini reasoning models do accept it.
    entry = get_llm_config("gemini-3.1-pro-preview", temperature=0.7)["config_list"][0]
    assert entry["temperature"] == 0.7


def test_llm_config_passes_reasoning_effort_through() -> None:
    """litellm drops reasoning_effort per model, so we never gate it here."""
    for model in ["o4-mini", "gemini-3.1-pro-preview", "gpt-4o"]:
        entry = get_llm_config(model, reasoning_effort="high")["config_list"][0]
        assert entry["reasoning_effort"] == "high"


def _response(content: str = '{"ok": true}') -> SimpleNamespace:
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=4, total_tokens=14),
        model="gpt-4o",
        _hidden_params={"response_cost": 0.25},
    )


def test_ag2_client_calls_litellm_with_the_resolved_spec(monkeypatch) -> None:
    calls = []

    def fake_complete(spec, messages, **kwargs):
        calls.append((str(spec), messages, kwargs))
        return _response()

    monkeypatch.setattr("autodiscovery.agents.llm.complete", fake_complete)
    monkeypatch.setattr("autodiscovery.agents.record_ag2_response_usage", lambda *a, **k: None)

    client = LiteLLMAG2Client({"model": "github_copilot/claude-haiku-4.5"})
    response = client.create(
        {"messages": [{"role": "user", "content": "hi"}], "temperature": 0.5, "n": 2}
    )

    model, messages, kwargs = calls[0]
    assert model == "github_copilot/claude-haiku-4.5"
    assert messages == [{"role": "user", "content": "hi"}]
    assert kwargs == {"temperature": 0.5, "n": 2}
    assert client.message_retrieval(response) == ['{"ok": true}']


def test_ag2_client_drops_temperature_for_openai_reasoning_models(monkeypatch) -> None:
    captured = {}

    monkeypatch.setattr(
        "autodiscovery.agents.llm.complete",
        lambda spec, messages, **kwargs: captured.update(kwargs) or _response(),
    )
    monkeypatch.setattr("autodiscovery.agents.record_ag2_response_usage", lambda *a, **k: None)

    LiteLLMAG2Client({"model": "o4-mini"}).create(
        {"messages": [{"role": "user", "content": "hi"}], "temperature": 0.5}
    )

    assert "temperature" not in captured


def test_ag2_client_reports_usage_and_cost() -> None:
    usage = LiteLLMAG2Client.get_usage(_response())

    assert usage["prompt_tokens"] == 10
    assert usage["completion_tokens"] == 4
    assert usage["total_tokens"] == 14
    assert usage["cost"] == 0.25


def test_ag2_client_records_usage_for_every_response(monkeypatch) -> None:
    """AG2 usage no longer depends on monkeypatching AG2's OpenAIWrapper."""
    recorded = []

    monkeypatch.setattr(
        "autodiscovery.agents.llm.complete", lambda spec, messages, **kwargs: _response()
    )
    monkeypatch.setattr(
        "autodiscovery.agents.record_ag2_response_usage",
        lambda response, **kwargs: recorded.append(response),
    )

    LiteLLMAG2Client({"model": "gpt-4o"}).create({"messages": [{"role": "user", "content": "x"}]})

    assert len(recorded) == 1


def test_llm_config_rejects_an_unusable_provider() -> None:
    from autodiscovery.model_spec import ModelSpecError

    with pytest.raises(ModelSpecError):
        get_llm_config("nonprovider/some-model")
