"""Tests for provider/model selection via litellm naming conventions."""

from argparse import Namespace

import pytest
from autodiscovery.args import ArgParser
from autodiscovery.easy import build_parser
from autodiscovery.llm import (
    ModelError,
    accepts_temperature,
    max_n,
    model_info,
    normalize_reasoning_effort,
    provider_of,
    validate,
)
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


# --- provider_of -----------------------------------------------------------


@pytest.mark.parametrize(
    ("model", "provider"),
    [
        ("vertex_ai/gemini-3.1-pro-preview", "vertex_ai"),
        ("vertex_ai/gemini-3-flash-preview", "vertex_ai"),
        ("openai/o4-mini", "openai"),
        ("openai/gpt-4o", "openai"),
        ("openai/text-embedding-3-large", "openai"),
        ("github_copilot/claude-haiku-4.5", "github_copilot"),
    ],
)
def test_provider_of_reads_the_prefix(model: str, provider: str) -> None:
    assert provider_of(model) == provider


@pytest.mark.parametrize(
    "model",
    [
        "gemini-3.1-pro-preview",
        "o4-mini",
        "gpt-4o",
        "text-embedding-3-large",
        # google/ was Vertex's OpenAI-compatible wire prefix, never a litellm one.
        "google/gemini-3.1-pro-preview",
    ],
)
def test_unqualified_and_non_litellm_names_are_rejected(model: str) -> None:
    """Names are rejected rather than guessed at."""
    with pytest.raises(ModelError):
        provider_of(model)


def test_unqualified_name_error_names_the_qualified_form() -> None:
    """The error should say exactly what to write instead."""
    with pytest.raises(ModelError, match=r"vertex_ai/gemini-3\.1-pro-preview"):
        provider_of("gemini-3.1-pro-preview")


def test_non_litellm_prefix_is_rejected() -> None:
    with pytest.raises(ModelError, match="not a litellm provider"):
        provider_of("nonprovider/some-model")


def test_any_litellm_provider_is_accepted() -> None:
    """No whitelist: providers beyond the three we document are usable.

    Supplying their credentials is the operator's job, per litellm's own env-var
    conventions. Only the slug is checked, so a typo still fails at startup.
    """
    assert provider_of("anthropic/claude-haiku-4.5") == "anthropic"
    assert provider_of("bedrock/anthropic.claude-3-sonnet-20240229-v1:0") == "bedrock"
    assert provider_of("ollama/llama3") == "ollama"
    assert provider_of("github_copilot/claude-haiku-4.5") == "github_copilot"


def test_models_litellm_has_not_mapped_still_resolve() -> None:
    """A model newer than the pinned litellm resolves from its prefix alone."""
    assert provider_of("vertex_ai/gemini-4.7-pro-preview") == "vertex_ai"
    assert model_info("vertex_ai/gemini-4.7-pro-preview") is None


# --- the three rules litellm cannot express --------------------------------


def test_accepts_temperature_only_excludes_openai_reasoning_models() -> None:
    """litellm claims o4-mini accepts temperature; the API rejects it."""
    assert not accepts_temperature("openai/o4-mini")
    assert not accepts_temperature("openai/gpt-5-mini")
    assert accepts_temperature("openai/gpt-4o")
    # Gemini reasoning models do take a temperature.
    assert accepts_temperature("vertex_ai/gemini-3.1-pro-preview")
    assert accepts_temperature("github_copilot/claude-haiku-4.5")


def test_max_n_is_capped_per_provider() -> None:
    """litellm's registry has no field for a per-request sample cap."""
    assert max_n("vertex_ai/gemini-3.1-pro-preview") == 5
    assert max_n("openai/o4-mini") == 8
    assert max_n("openai/gpt-4o") is None


def test_minimal_reasoning_effort_uses_the_registry_not_a_name_prefix() -> None:
    """Downgrade minimal->low only where the model really lacks it.

    The old ``startswith("o")/"gpt-5"`` test downgraded the whole gpt-5 family,
    which does accept ``minimal``. litellm records that per model.
    """
    assert normalize_reasoning_effort("openai/o4-mini", "minimal") == "low"
    assert normalize_reasoning_effort("openai/gpt-5-mini", "minimal") == "minimal"
    # Gemini and Copilot pass the caller's value through.
    assert normalize_reasoning_effort("vertex_ai/gemini-3-flash-preview", "minimal") == "minimal"
    assert normalize_reasoning_effort("github_copilot/claude-haiku-4.5", "minimal") == "minimal"
    assert normalize_reasoning_effort("openai/o4-mini", "high") == "high"
    assert normalize_reasoning_effort("openai/o4-mini", None) is None


# --- validate --------------------------------------------------------------


def test_validate_rejects_a_vision_model_without_image_support() -> None:
    with pytest.raises(ModelError, match="does not support image input"):
        validate("openai/gpt-3.5-turbo", flag="--vision_model", require_vision=True)
    # The same model is fine when vision is not required.
    validate("openai/gpt-3.5-turbo", flag="--model")


def test_validate_rejects_a_mode_mismatch() -> None:
    with pytest.raises(ModelError, match="'chat' model is required"):
        validate("openai/text-embedding-3-large", flag="--model")
    with pytest.raises(ModelError, match="'embedding' model is required"):
        validate("openai/gpt-4o", flag="--embedding_model", mode="embedding")


def test_copilot_validation_prefers_the_accounts_live_catalog(monkeypatch) -> None:
    """litellm's static Copilot catalog is not authoritative in either direction.

    It lists models an account cannot call (``gpt-5`` returns "The requested
    model is not supported") and omits ones it can (``gpt-5.4``). Copilot's own
    ``/models`` endpoint is the real answer, so validation uses it when it can be
    read from litellm's cached key without authenticating.
    """
    live = {
        "gpt-4.1": {"capabilities": {"supports": {"vision": True}}},
        "gpt-5.4": {"capabilities": {"supports": {"vision": True}}},
        "gpt-4o-mini": {"capabilities": {"supports": {}}},
    }
    monkeypatch.setattr("autodiscovery.llm._copilot_live_catalog", lambda: live)

    # In litellm's catalog but not callable by this account.
    with pytest.raises(ModelError, match="not available to this Copilot account"):
        validate("github_copilot/gpt-5", flag="--model")
    # Callable but absent from litellm's catalog -- must not be rejected.
    validate("github_copilot/gpt-5.4", flag="--model")
    # Vision comes from the live entry, not litellm's registry.
    validate("github_copilot/gpt-4.1", flag="--vision_model", require_vision=True)
    with pytest.raises(ModelError, match="does not support image input"):
        validate("github_copilot/gpt-4o-mini", flag="--vision_model", require_vision=True)


def test_copilot_validation_falls_back_when_the_live_catalog_is_unavailable(monkeypatch) -> None:
    """No cached Copilot key means no live list; fall back to litellm's registry."""
    monkeypatch.setattr("autodiscovery.llm._copilot_live_catalog", lambda: None)

    validate("github_copilot/gpt-4.1", flag="--model")


def test_copilot_live_catalog_never_authenticates(monkeypatch, tmp_path) -> None:
    """Reading the live list must not be able to trigger the device flow."""
    from litellm.llms.github_copilot.authenticator import Authenticator

    def fail(*args, **kwargs):
        raise AssertionError("live catalog lookup attempted authentication")

    monkeypatch.setattr(Authenticator, "get_api_key", fail)
    monkeypatch.setattr(Authenticator, "get_access_token", fail)
    monkeypatch.setattr(Authenticator, "_login", fail)
    # Point at an empty dir so there is no cached key to read.
    monkeypatch.setenv("GITHUB_COPILOT_TOKEN_DIR", str(tmp_path))

    from autodiscovery.llm import _copilot_live_catalog

    _copilot_live_catalog.cache_clear()
    try:
        assert _copilot_live_catalog() is None
    finally:
        _copilot_live_catalog.cache_clear()


def test_validate_allows_models_litellm_has_not_mapped() -> None:
    """Open-catalog providers ship models before litellm maps them."""
    validate("vertex_ai/gemini-4.7-pro-preview", flag="--model")


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

    validate("github_copilot/claude-haiku-4.5", flag="--model", require_vision=True)


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

    assert provider_of(args.model) == "github_copilot"
    assert provider_of(args.vision_model) == "vertex_ai"


def test_unqualified_model_flag_fails_at_startup() -> None:
    args = engine_args("--model", "gemini-3.1-pro-preview")

    with pytest.raises(ModelError, match="missing a provider"):
        resolve_model_args(args)
