"""Tests for provider/model selection via litellm naming conventions."""

from argparse import Namespace

import pytest
from autodiscovery.args import ArgParser
from autodiscovery.easy import build_parser
from autodiscovery.model_spec import ModelSpecError, parse_model, validate_model
from autodiscovery.run import resolve_model_args


def engine_args(*extra: str) -> Namespace:
    return ArgParser().parse_args(
        [
            "--dataset_metadata",
            "metadata.json",
            "--out_dir",
            "results",
            "--work_dir",
            "work",
            "--n_experiments",
            "1",
            *extra,
        ]
    )


# --- parse_model -----------------------------------------------------------


@pytest.mark.parametrize(
    ("spec", "provider", "model"),
    [
        ("vertex_ai/gemini-3.1-pro-preview", "vertex_ai", "gemini-3.1-pro-preview"),
        ("vertex_ai/gemini-3-flash-preview", "vertex_ai", "gemini-3-flash-preview"),
        ("openai/o4-mini", "openai", "o4-mini"),
        ("openai/gpt-4o", "openai", "gpt-4o"),
        ("openai/text-embedding-3-large", "openai", "text-embedding-3-large"),
        ("github_copilot/claude-haiku-4.5", "github_copilot", "claude-haiku-4.5"),
    ],
)
def test_parse_model_resolves_provider(spec: str, provider: str, model: str) -> None:
    resolved = parse_model(spec)

    assert (resolved.provider, resolved.model) == (provider, model)
    assert str(resolved) == spec


@pytest.mark.parametrize(
    "spec",
    [
        "gemini-3.1-pro-preview",
        "o4-mini",
        "gpt-4o",
        "text-embedding-3-large",
        # google/ was Vertex's OpenAI-compatible wire prefix, never a litellm one.
        "google/gemini-3.1-pro-preview",
    ],
)
def test_parse_model_requires_a_litellm_provider_prefix(spec: str) -> None:
    """Unqualified and non-litellm names are rejected rather than guessed at."""
    with pytest.raises(ModelSpecError):
        parse_model(spec)


def test_unqualified_name_error_names_the_qualified_form() -> None:
    """The error should say exactly what to write instead."""
    with pytest.raises(ModelSpecError, match=r"vertex_ai/gemini-3\.1-pro-preview"):
        parse_model("gemini-3.1-pro-preview")


def test_parse_model_rejects_non_litellm_prefix() -> None:
    with pytest.raises(ModelSpecError, match="not a litellm provider"):
        parse_model("nonprovider/some-model")


def test_parse_model_rejects_provider_without_a_transport() -> None:
    """Anthropic direct is a real litellm provider, but not one we route to."""
    with pytest.raises(ModelSpecError, match="no transport for"):
        parse_model("anthropic/claude-haiku-4.5")
    assert parse_model("github_copilot/claude-haiku-4.5").is_copilot


def test_parse_model_accepts_models_litellm_has_not_mapped() -> None:
    """A model newer than the pinned litellm still resolves from its prefix."""
    resolved = parse_model("vertex_ai/gemini-4.7-pro-preview")

    assert resolved.is_vertex
    assert resolved.info is None


# --- capabilities ----------------------------------------------------------


def test_temperature_and_n_rules_are_provider_derived() -> None:
    """The two rules litellm's registry cannot express."""
    o_series = parse_model("openai/o4-mini")
    assert not o_series.accepts_temperature
    assert o_series.max_n == 8

    gemini = parse_model("vertex_ai/gemini-3.1-pro-preview")
    # Gemini reasoning models still take a temperature; only OpenAI's reject it.
    assert gemini.accepts_temperature
    assert gemini.max_n == 5

    gpt4o = parse_model("openai/gpt-4o")
    assert gpt4o.accepts_temperature
    assert gpt4o.max_n is None


def test_minimal_reasoning_effort_uses_the_registry_not_a_name_prefix() -> None:
    """Downgrade minimal->low only where the model really lacks it.

    The old ``startswith("o")/"gpt-5"`` test downgraded the whole gpt-5 family,
    which does accept ``minimal``. litellm records that per model.
    """
    from autodiscovery.utils import normalize_reasoning_effort

    assert normalize_reasoning_effort(parse_model("openai/o4-mini"), "minimal") == "low"
    assert normalize_reasoning_effort(parse_model("openai/gpt-5-mini"), "minimal") == "minimal"
    # Gemini passes the caller's value through.
    assert (
        normalize_reasoning_effort(parse_model("vertex_ai/gemini-3-flash-preview"), "minimal")
        == "minimal"
    )
    assert normalize_reasoning_effort(parse_model("openai/o4-mini"), "high") == "high"
    assert normalize_reasoning_effort(parse_model("openai/o4-mini"), None) is None


# --- validate_model --------------------------------------------------------


def test_validate_model_rejects_a_vision_model_without_image_support() -> None:
    with pytest.raises(ModelSpecError, match="does not support image input"):
        validate_model("openai/gpt-3.5-turbo", flag="--vision_model", require_vision=True)
    # The same model is fine when vision is not required.
    assert validate_model("openai/gpt-3.5-turbo", flag="--model").is_openai


def test_validate_model_rejects_a_mode_mismatch() -> None:
    with pytest.raises(ModelSpecError, match="'chat' model is required"):
        validate_model("openai/text-embedding-3-large", flag="--model")
    with pytest.raises(ModelSpecError, match="'embedding' model is required"):
        validate_model("openai/gpt-4o", flag="--embedding_model", mode="embedding")


def test_validate_model_rejects_a_model_missing_from_copilots_catalog() -> None:
    """Copilot's litellm catalog is a complete enumeration, so absence is an error."""
    with pytest.raises(ModelSpecError, match="not in github_copilot's catalog"):
        validate_model("github_copilot/gemini-3.1-pro-preview", flag="--model")


def test_validate_model_allows_models_litellm_has_not_mapped() -> None:
    """Open-catalog providers ship models before litellm maps them."""
    resolved = validate_model("vertex_ai/gemini-4.7-pro-preview", flag="--model")

    assert resolved.is_vertex
    assert resolved.info is None


def test_validation_never_triggers_copilot_device_flow(monkeypatch) -> None:
    """litellm must not run GitHub's interactive auth during validation.

    ``litellm.get_llm_provider()`` and the ``litellm.supports_*()`` helpers run
    GitHub's device-flow login for ``github_copilot/`` models -- they print a
    device code and block for three 60s attempts, with no env var to disable it.
    Requiring a provider prefix means the resolver is never called at all, and
    capability lookups pass ``custom_llm_provider`` explicitly. This test fails
    if anything reintroduces an authenticating litellm call.
    """
    from litellm.llms.github_copilot.authenticator import Authenticator

    def fail(*args, **kwargs):
        raise AssertionError("model resolution attempted GitHub Copilot authentication")

    monkeypatch.setattr(Authenticator, "get_api_key", fail)
    monkeypatch.setattr(Authenticator, "get_access_token", fail)
    monkeypatch.setattr(Authenticator, "_login", fail)

    resolved = validate_model("github_copilot/claude-haiku-4.5", flag="--model")
    assert resolved.is_copilot
    assert resolved.supports_vision


# --- CLI boundary ----------------------------------------------------------


def test_engine_defaults_are_litellm_qualified() -> None:
    args = engine_args()

    assert args.model == "vertex_ai/gemini-3.1-pro-preview"
    assert args.belief_model == "vertex_ai/gemini-3-flash-preview"
    assert args.vision_model == "vertex_ai/gemini-3.1-pro-preview"
    assert args.embedding_model == "openai/text-embedding-3-large"
    resolve_model_args(args)


def test_easy_cli_shares_the_engine_model_defaults() -> None:
    args = build_parser().parse_args(["--out_dir", "results", "--n_experiments", "1", "data.csv"])

    assert args.model == "vertex_ai/gemini-3.1-pro-preview"
    assert args.belief_model == "vertex_ai/gemini-3-flash-preview"
    assert args.vision_model == "vertex_ai/gemini-3.1-pro-preview"
    assert args.embedding_model == "openai/text-embedding-3-large"


@pytest.mark.parametrize("flag", ["--llm_provider", "--embedding_provider"])
def test_provider_flags_are_gone(flag: str) -> None:
    """Both flags were replaced by the provider prefix on each model flag."""
    with pytest.raises(SystemExit):
        engine_args(flag, "copilot")


def test_mixed_provider_runs_are_expressible() -> None:
    """One flag per role, so chat and vision need not share a provider."""
    args = engine_args(
        "--model",
        "github_copilot/claude-haiku-4.5",
        "--vision_model",
        "vertex_ai/gemini-3.1-pro-preview",
    )
    resolve_model_args(args)

    assert parse_model(args.model).is_copilot
    assert parse_model(args.vision_model).is_vertex


def test_unqualified_model_flag_fails_at_startup() -> None:
    args = engine_args("--model", "gemini-3.1-pro-preview")

    with pytest.raises(ModelSpecError, match="missing a provider"):
        resolve_model_args(args)
