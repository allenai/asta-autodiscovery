"""Tests for provider-related CLI arguments."""

from autodiscovery.agents import get_agents
from autodiscovery.args import ArgParser
from autodiscovery.easy import build_parser


def test_engine_provider_defaults_preserve_model_name_routing() -> None:
    args = ArgParser().parse_args(
        [
            "--dataset_metadata",
            "metadata.json",
            "--out_dir",
            "results",
            "--work_dir",
            "work",
            "--n_experiments",
            "1",
        ]
    )

    assert args.llm_provider is None
    assert args.embedding_provider is None
    assert args.embedding_model is None
    assert args.embedding_dimensions is None


def test_easy_cli_provider_defaults_preserve_model_name_routing() -> None:
    args = build_parser().parse_args(
        [
            "--out_dir",
            "results",
            "--n_experiments",
            "1",
            "data.csv",
        ]
    )

    assert args.llm_provider is None
    assert args.embedding_provider is None


def test_easy_cli_accepts_copilot_provider_and_embedding_options() -> None:
    args = build_parser().parse_args(
        [
            "--out_dir",
            "results",
            "--n_experiments",
            "1",
            "--llm_provider",
            "copilot",
            "--embedding_provider",
            "copilot",
            "--embedding_model",
            "text-embedding-3-small",
            "--embedding_dimensions",
            "1536",
            "--dedupe",
            "data.csv",
        ]
    )

    assert args.llm_provider == "copilot"
    assert args.embedding_provider == "copilot"
    assert args.embedding_model == "text-embedding-3-small"
    assert args.embedding_dimensions == 1536
    assert args.dedupe is True


def test_get_agents_rejects_unknown_provider_before_credentials() -> None:
    try:
        get_agents("work", llm_provider="unknown")
    except ValueError as exc:
        assert str(exc) == "Unknown LLM provider: unknown"
    else:
        raise AssertionError("Expected an unknown provider to be rejected")
