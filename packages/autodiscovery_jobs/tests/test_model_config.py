"""Tests for the model-choice startup gate (``model_config``)."""

import pytest
from autodiscovery_jobs.exceptions import ModelConfigError
from autodiscovery_jobs.model_config import check_model_config, chosen_model, provider_of

# A minimal, complete environment per documented provider, docker job backend.
OPENAI = {"AUTODISCOVERY_MODEL": "openai/gpt-5.4-mini", "OPENAI_API_KEY": "sk-test"}
ANTHROPIC = {"AUTODISCOVERY_MODEL": "anthropic/claude-sonnet-5", "ANTHROPIC_API_KEY": "ant-test"}
AZURE = {
    "AUTODISCOVERY_MODEL": "azure/gpt-5.4-mini",
    "AZURE_API_KEY": "az-test",
    "AZURE_API_BASE": "https://example.openai.azure.com",
}
VERTEX = {
    "AUTODISCOVERY_MODEL": "vertex_ai/gemini-3.7-flash",
    "VERTEXAI_PROJECT": "test-project",
    "VERTEXAI_LOCATION": "global",
    "GCP_KEY_HOST_PATH": "/host/secrets/gcp-key.json",
}
COPILOT = {
    "AUTODISCOVERY_MODEL": "github_copilot/claude-haiku-4.5",
    "GITHUB_COPILOT_TOKEN_HOST_DIR": "/host/home/.config/litellm/github_copilot",
}


def test_no_model_is_refused():
    with pytest.raises(ModelConfigError, match="No model chosen"):
        check_model_config(env={})


def test_a_blank_model_counts_as_unset():
    with pytest.raises(ModelConfigError, match="No model chosen"):
        check_model_config(env={"AUTODISCOVERY_MODEL": "  "})


@pytest.mark.parametrize("model", ["gpt-5.4-mini", "openai/", "/gpt-5.4-mini"])
def test_an_unqualified_model_is_refused(model):
    with pytest.raises(ModelConfigError, match="missing its provider"):
        check_model_config(env={"AUTODISCOVERY_MODEL": model, "OPENAI_API_KEY": "k"})


def test_an_unqualified_role_override_is_refused():
    with pytest.raises(ModelConfigError, match="AUTODISCOVERY_VISION_MODEL=gpt-4o"):
        check_model_config(env={**OPENAI, "AUTODISCOVERY_VISION_MODEL": "gpt-4o"})


@pytest.mark.parametrize("env", [OPENAI, ANTHROPIC, AZURE, VERTEX, COPILOT])
def test_each_documented_provider_has_a_minimal_configuration(env):
    """The quick-start examples: model plus that provider's variables, nothing else."""
    assert check_model_config(env=env) == env["AUTODISCOVERY_MODEL"]


@pytest.mark.parametrize(
    ("env", "missing"),
    [
        (OPENAI, "OPENAI_API_KEY"),
        (ANTHROPIC, "ANTHROPIC_API_KEY"),
        (AZURE, "AZURE_API_BASE"),
        (VERTEX, "VERTEXAI_LOCATION"),
        (VERTEX, "GCP_KEY_HOST_PATH"),
        (COPILOT, "GITHUB_COPILOT_TOKEN_HOST_DIR"),
    ],
)
def test_docker_backend_needs_the_providers_variables(env, missing):
    """The docker backend forwards the API's own environment to each job."""
    incomplete = {k: v for k, v in env.items() if k != missing}

    with pytest.raises(ModelConfigError, match=missing):
        check_model_config(env=incomplete)


def test_a_role_override_is_checked_for_its_own_provider():
    env = {**ANTHROPIC, "AUTODISCOVERY_EMBEDDING_MODEL": "openai/text-embedding-3-large"}

    with pytest.raises(ModelConfigError, match="OPENAI_API_KEY"):
        check_model_config(env=env)
    check_model_config(env={**env, "OPENAI_API_KEY": "sk-test"})


def test_the_gcp_backend_holds_no_provider_credentials():
    """Cloud Run jobs carry their own secrets, so only the choice itself is checked."""
    env = {"AUTODISCOVERY_MODEL": "openai/gpt-5.4-mini", "JOB_BACKEND": "gcp"}

    assert check_model_config(env=env) == "openai/gpt-5.4-mini"
    assert check_model_config(env={"AUTODISCOVERY_MODEL": "openai/x"}, job_backend="GCP")


def test_undocumented_litellm_providers_are_accepted_unchecked():
    assert check_model_config(env={"AUTODISCOVERY_MODEL": "ollama/llama3"}) == "ollama/llama3"


def test_chosen_model_reads_roles():
    env = {"AUTODISCOVERY_MODEL": "a/b", "AUTODISCOVERY_BELIEF_MODEL": " c/d "}
    assert chosen_model(env=env) == "a/b"
    assert chosen_model("belief_model", env=env) == "c/d"
    assert chosen_model("vision_model", env=env) is None


def test_provider_of():
    assert provider_of("openai/gpt-5.4-mini") == "openai"
    assert provider_of("gpt-5.4-mini") is None
    assert provider_of("openai/") is None
