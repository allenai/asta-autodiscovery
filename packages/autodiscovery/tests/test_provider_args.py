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
        # Bare names keep resolving the way existing deployment configs expect.
        ("gemini-3.1-pro-preview", "vertex_ai", "gemini-3.1-pro-preview"),
        ("gemini-3-flash-preview", "vertex_ai", "gemini-3-flash-preview"),
        ("o4-mini", "openai", "o4-mini"),
        ("gpt-4o", "openai", "gpt-4o"),
        ("text-embedding-3-large", "openai", "text-embedding-3-large"),
        # litellm's own convention.
        ("vertex_ai/gemini-3.1-pro-preview", "vertex_ai", "gemini-3.1-pro-preview"),
        ("openai/o4-mini", "openai", "o4-mini"),
        ("github_copilot/claude-haiku-4.5", "github_copilot", "claude-haiku-4.5"),
        # google/ is a Vertex wire-format detail retained as a legacy alias.
        ("google/gemini-3.1-pro-preview", "vertex_ai", "gemini-3.1-pro-preview"),
    ],
)
def test_parse_model_resolves_provider(spec: str, provider: str, model: str) -> None:
    resolved = parse_model(spec)
    assert (resolved.provider, resolved.model) == (provider, model)


def test_parse_model_rejects_non_litellm_prefix() -> None:
    with pytest.raises(ModelSpecError, match="not a litellm provider"):
        parse_model("nonprovider/some-model")


def test_parse_model_rejects_provider_without_a_transport() -> None:
    # litellm resolves a bare claude-* name to Anthropic direct, which this
    # package cannot call. The Copilot-hosted model must be named explicitly.
    with pytest.raises(ModelSpecError, match="no transport for"):
        parse_model("claude-haiku-4.5")
    assert parse_model("github_copilot/claude-haiku-4.5").is_copilot


def test_parse_model_falls_back_for_models_litellm_has_not_mapped() -> None:
    """A model newer than the pinned litellm must not break an existing config."""
    assert parse_model("gemini-4.7-pro-preview").is_vertex
    assert parse_model("some-unmapped-model").is_openai


def test_default_provider_namespaces_bare_names() -> None:
    resolved = parse_model("claude-haiku-4.5", default_provider="copilot")
    assert str(resolved) == "github_copilot/claude-haiku-4.5"


# --- capabilities ----------------------------------------------------------


def test_wire_model_name_keeps_the_google_prefix_internal_to_vertex() -> None:
    assert parse_model("gemini-3.1-pro-preview").wire_model_name == "google/gemini-3.1-pro-preview"
    assert parse_model("o4-mini").wire_model_name == "o4-mini"
    assert parse_model("github_copilot/claude-haiku-4.5").wire_model_name == "claude-haiku-4.5"


def test_temperature_and_reasoning_match_pre_litellm_behavior() -> None:
    o_series = parse_model("o4-mini")
    assert o_series.supports_reasoning
    assert not o_series.accepts_temperature
    assert o_series.max_n == 8

    gemini = parse_model("gemini-3.1-pro-preview")
    assert gemini.supports_reasoning
    # Gemini reasoning models still take a temperature; only OpenAI's reject it.
    assert gemini.accepts_temperature
    assert gemini.max_n == 5

    gpt4o = parse_model("gpt-4o")
    assert not gpt4o.supports_reasoning
    assert gpt4o.accepts_temperature
    assert gpt4o.max_n is None


# --- validate_model --------------------------------------------------------


def test_validate_model_rejects_a_vision_model_without_image_support() -> None:
    with pytest.raises(ModelSpecError, match="does not support image input"):
        validate_model("gpt-3.5-turbo", flag="--vision_model", require_vision=True)
    # The same model is fine when vision is not required.
    assert validate_model("gpt-3.5-turbo", flag="--model").is_openai


def test_validate_model_rejects_a_mode_mismatch() -> None:
    with pytest.raises(ModelSpecError, match="'chat' model is required"):
        validate_model("text-embedding-3-large", flag="--model")
    with pytest.raises(ModelSpecError, match="'embedding' model is required"):
        validate_model("gpt-4o", flag="--embedding_model", mode="embedding")


def test_validate_model_allows_models_litellm_has_not_mapped() -> None:
    resolved = validate_model("gemini-4.7-pro-preview", flag="--model")
    assert resolved.is_vertex
    assert not resolved.is_known


# --- CLI boundary ----------------------------------------------------------


def test_engine_defaults_resolve_to_the_providers_used_today() -> None:
    args = engine_args()
    resolve_model_args(args)

    assert args.model == "vertex_ai/gemini-3.1-pro-preview"
    assert args.belief_model == "vertex_ai/gemini-3-flash-preview"
    assert args.vision_model == "vertex_ai/gemini-3.1-pro-preview"
    assert args.embedding_model == "openai/text-embedding-3-large"


def test_prefixed_model_flags_survive_the_boundary() -> None:
    args = engine_args(
        "--model",
        "github_copilot/claude-haiku-4.5",
        "--belief_model",
        "openai/gpt-4o",
        "--vision_model",
        "github_copilot/gemini-3-pro-preview",
        "--embedding_model",
        "github_copilot/text-embedding-3-small",
    )
    resolve_model_args(args)

    assert args.model == "github_copilot/claude-haiku-4.5"
    assert args.belief_model == "openai/gpt-4o"
    assert args.vision_model == "github_copilot/gemini-3-pro-preview"
    assert args.embedding_model == "github_copilot/text-embedding-3-small"


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


def test_deprecated_provider_flags_still_namespace_bare_model_names() -> None:
    args = engine_args(
        "--llm_provider",
        "copilot",
        "--embedding_provider",
        "copilot",
        "--model",
        "claude-haiku-4.5",
        "--belief_model",
        "gpt-4o",
        "--vision_model",
        "gemini-3-pro-preview",
    )
    resolve_model_args(args)

    assert args.model == "github_copilot/claude-haiku-4.5"
    assert args.belief_model == "github_copilot/gpt-4o"
    assert args.vision_model == "github_copilot/gemini-3-pro-preview"
    # Copilot's catalog has no text-embedding-3-large, so it gets its own default.
    assert args.embedding_model == "github_copilot/text-embedding-3-small"


def test_copilot_provider_flag_with_default_models_fails_at_startup() -> None:
    """The #59 failure mode, now caught before the first model call.

    ``--llm_provider copilot`` with the default ``--model
    gemini-3.1-pro-preview`` used to fail partway into a run; Copilot's catalog
    has ``gemini-3-pro-preview``, not ``gemini-3.1-pro-preview``.
    """
    args = engine_args("--llm_provider", "copilot")
    with pytest.raises(ModelSpecError, match="not in github_copilot's catalog"):
        resolve_model_args(args)


def test_easy_cli_shares_the_engine_model_defaults() -> None:
    args = build_parser().parse_args(["--out_dir", "results", "--n_experiments", "1", "data.csv"])

    assert args.model == "gemini-3.1-pro-preview"
    assert args.belief_model == "gemini-3-flash-preview"
    assert args.vision_model == "gemini-3.1-pro-preview"
    assert args.llm_provider is None
    assert args.embedding_provider is None


def test_easy_cli_accepts_prefixed_models() -> None:
    args = build_parser().parse_args(
        [
            "--out_dir",
            "results",
            "--n_experiments",
            "1",
            "--model",
            "github_copilot/claude-haiku-4.5",
            "--embedding_model",
            "github_copilot/text-embedding-3-small",
            "--embedding_dimensions",
            "1536",
            "--dedupe",
            "data.csv",
        ]
    )

    assert args.model == "github_copilot/claude-haiku-4.5"
    assert args.embedding_model == "github_copilot/text-embedding-3-small"
    assert args.embedding_dimensions == 1536
    assert args.dedupe is True


def test_resolution_never_triggers_copilot_device_flow(monkeypatch) -> None:
    """litellm must not run GitHub's interactive auth during model resolution.

    ``litellm.get_llm_provider()`` and the ``litellm.supports_*()`` helpers run
    GitHub's device-flow login for ``github_copilot/`` models -- they print a
    device code and block for three 60s attempts. There is no litellm env var to
    disable that, so it would hang any deployed (non-TTY) run. model_spec avoids
    it by splitting the provider prefix itself and only reading litellm's static
    registry; this test fails if anything reintroduces an authenticating call.
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
    assert resolved.mode == "chat"
    with pytest.raises(ModelSpecError, match="not in github_copilot's catalog"):
        validate_model("github_copilot/gemini-3.1-pro-preview", flag="--model")
