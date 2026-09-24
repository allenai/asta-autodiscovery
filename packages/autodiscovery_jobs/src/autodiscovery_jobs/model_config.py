"""The operator's model choice, and the startup gate that enforces it.

There is no default model. The operator picks one with ``AUTODISCOVERY_MODEL``
(litellm's ``<provider>/<model>``), optionally overriding a role with
``AUTODISCOVERY_BELIEF_MODEL``, ``AUTODISCOVERY_VISION_MODEL`` or
``AUTODISCOVERY_EMBEDDING_MODEL``. The launcher passes the choice to every job
as explicit ``--model`` flags (see ``backends.base.build_job_args``), so the job
image needs no model configuration of its own on any job backend.

:func:`check_model_config` is the API's startup gate. It refuses to start when
no model is chosen, when a name lacks its provider prefix, or -- on the docker
job backend, whose jobs get their credentials forwarded from the API's own
environment -- when the chosen provider's variables are missing. Without it the
stack would come up and fail only once a run was submitted.

This module deliberately imports neither litellm nor the engine, so the API
image stays small; the job repeats the provider check against litellm's
registry itself (``autodiscovery.llm.validate``), which keeps the copy of the
per-provider table there.
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from .exceptions import ModelConfigError

#: The one required choice.
MODEL_ENV = "AUTODISCOVERY_MODEL"

#: Optional per-role overrides, keyed by the job's flag name.
ROLE_ENV = {
    "belief_model": "AUTODISCOVERY_BELIEF_MODEL",
    "vision_model": "AUTODISCOVERY_VISION_MODEL",
    "embedding_model": "AUTODISCOVERY_EMBEDDING_MODEL",
}

#: Per provider, the API-environment variables the docker job backend forwards
#: (or bind-mounts) into each job, without which that provider cannot be called
#: from a job container. The ``*_HOST_*`` names are the host paths compose
#: forwards for bind mounts (see ``docker-compose.yaml`` and ``backends/docker.py``).
#: Any other litellm provider is accepted unchecked; its credentials are the
#: operator's job, per litellm's own conventions.
PROVIDER_ENV: dict[str, tuple[str, ...]] = {
    "openai": ("OPENAI_API_KEY",),
    "azure": ("AZURE_API_KEY", "AZURE_API_BASE"),
    "anthropic": ("ANTHROPIC_API_KEY",),
    "vertex_ai": ("VERTEXAI_PROJECT", "VERTEXAI_LOCATION", "GCP_KEY_HOST_PATH"),
    "github_copilot": ("GITHUB_COPILOT_TOKEN_HOST_DIR",),
}

QUICKSTART = "docs/quickstart.md"


def chosen_model(role: str | None = None, env: Mapping[str, str] | None = None) -> str | None:
    """Return the model the environment names for a role, or None if unset.

    Args:
        role: ``None`` for the main model, else a key of :data:`ROLE_ENV`.
        env: Environment to read; defaults to ``os.environ``.

    Returns:
        The stripped value, or None when the variable is unset or blank.
    """
    env = os.environ if env is None else env
    value = env.get(MODEL_ENV if role is None else ROLE_ENV[role], "").strip()
    return value or None


def provider_of(model: str) -> str | None:
    """Return the ``<provider>`` prefix of a litellm model name, or None if it has none."""
    provider, sep, remainder = model.strip().partition("/")
    return provider if sep and provider and remainder else None


def check_model_config(env: Mapping[str, str] | None = None, job_backend: str | None = None) -> str:
    """Check the environment names a usable model; raise otherwise.

    Args:
        env: Environment to read; defaults to ``os.environ``.
        job_backend: The active job backend; defaults to ``JOB_BACKEND`` in
            ``env``, else ``docker``. Provider variables are only checked for
            ``docker``, where the API's environment is what jobs receive.

    Returns:
        The chosen main model.

    Raises:
        ModelConfigError: If no model is chosen, a model lacks its provider
            prefix, or (docker backend) the provider's variables are unset.
    """
    env = os.environ if env is None else env

    model = chosen_model(env=env)
    if model is None:
        raise ModelConfigError(
            f"No model chosen. Set {MODEL_ENV}=<provider>/<model> in .env (for example "
            f"openai/gpt-5.4-mini) together with that provider's variables. See {QUICKSTART}."
        )

    models = {MODEL_ENV: model}
    for role in ROLE_ENV:
        if value := chosen_model(role, env=env):
            models[ROLE_ENV[role]] = value
    for var, value in models.items():
        if provider_of(value) is None:
            raise ModelConfigError(
                f"{var}={value} is missing its provider. Model names are litellm-qualified "
                f"as <provider>/<model>, e.g. openai/{value}. See {QUICKSTART}."
            )

    backend = (job_backend or env.get("JOB_BACKEND") or "docker").strip().lower()
    if backend != "docker":
        return model

    for var, value in models.items():
        provider = provider_of(value)
        assert provider is not None  # checked above
        missing = [name for name in PROVIDER_ENV.get(provider, ()) if not env.get(name)]
        if missing:
            raise ModelConfigError(
                f"{var}={value} needs {', '.join(missing)} set: the docker job backend "
                f"forwards the API's environment to each job, and the '{provider}' provider "
                f"cannot be called without it. See {QUICKSTART}."
            )
    return model
