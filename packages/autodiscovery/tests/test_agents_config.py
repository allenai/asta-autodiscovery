"""Tests for AG2 model config generation."""

from autodiscovery.agents import get_openai_config


def test_get_openai_config_gemini_uses_vertex_openai(monkeypatch) -> None:
    """Ensure Gemini agent config uses Vertex OpenAI-compatible settings."""
    monkeypatch.setenv("VERTEX_OPENAI_BASE_URL", "https://vertex.example/v1")
    monkeypatch.setenv("VERTEX_ACCESS_TOKEN", "vertex-token")

    config = get_openai_config(
        model_name="gemini-3-flash-preview",
        timeout=321,
        temperature=0.7,
    )

    assert config["api_type"] == "openai"
    assert config["model"] == "google/gemini-3-flash-preview"
    assert config["api_key"] == "vertex-token"
    assert config["base_url"] == "https://vertex.example/v1"
    assert config["timeout"] == 321
    assert config["temperature"] == 0.7
    assert "logprobs" not in config


def test_get_openai_config_openai_model_unchanged() -> None:
    """Ensure non-Gemini config still uses direct OpenAI settings."""
    config = get_openai_config(
        model_name="gpt-4o",
        timeout=600,
        temperature=0.2,
        api_key="openai-key",
    )

    assert config["api_type"] == "openai"
    assert config["model"] == "gpt-4o"
    assert config["api_key"] == "openai-key"
    assert config["timeout"] == 600
    assert config["temperature"] == 0.2
    assert config["logprobs"] is True
