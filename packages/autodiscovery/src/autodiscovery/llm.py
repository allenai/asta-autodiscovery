"""The single transport for every model call in this package.

All chat, vision and embedding traffic goes through ``litellm``, which owns
provider routing, auth, request/response shaping and retries. Nothing here
speaks a provider's wire protocol directly, so adding a provider is a matter of
naming it in a model flag rather than writing a client.

Provider credentials follow litellm's own conventions:

- ``vertex_ai`` uses Application Default Credentials. Set
  ``GOOGLE_APPLICATION_CREDENTIALS`` to a service-account key, or run
  ``gcloud auth application-default login`` locally. ``VERTEX_PROJECT_ID`` and
  ``VERTEX_LOCATION`` are mapped onto litellm's ``vertex_project`` /
  ``vertex_location`` so existing deployment env vars keep working.
- ``openai`` uses ``OPENAI_API_KEY``.
- ``github_copilot`` uses a GitHub OAuth token under
  ``$GITHUB_COPILOT_TOKEN_DIR/access-token`` (default
  ``~/.config/litellm/github_copilot``). See ``docs/autodiscovery/standalone.md``.
"""

from __future__ import annotations

import functools
import os
from typing import Any

from autodiscovery.llm_retry import load_retry_config
from autodiscovery.model_spec import VERTEX_AI, ModelSpec

VERTEX_PROJECT_ENV_VAR = "VERTEX_PROJECT_ID"
VERTEX_LOCATION_ENV_VAR = "VERTEX_LOCATION"

#: Per-request timeout, matching the previous AG2/OpenAI client default.
REQUEST_TIMEOUT_S = 600


@functools.cache
def _configure() -> Any:
    """Import and configure litellm once.

    Returns:
        The configured ``litellm`` module.
    """
    import litellm

    # Let litellm strip parameters a given model does not accept (for example
    # reasoning_effort on gpt-4o) instead of hand-maintaining that per call site.
    litellm.drop_params = True
    # We surface our own errors; litellm's provider-list banner is noise.
    litellm.suppress_debug_info = True

    litellm.num_retries = load_retry_config().max_retries
    return litellm


def _provider_kwargs(spec: ModelSpec) -> dict[str, Any]:
    """Return provider-scoped kwargs for a litellm call.

    Args:
        spec: Resolved model.

    Returns:
        Extra kwargs to pass to ``litellm.completion`` / ``litellm.embedding``.
    """
    if spec.provider != VERTEX_AI:
        return {}
    kwargs: dict[str, Any] = {}
    # Map this package's long-standing env vars onto litellm's parameter names
    # so existing deployment configuration keeps working unchanged.
    if project := os.getenv(VERTEX_PROJECT_ENV_VAR):
        kwargs["vertex_project"] = project
    if location := os.getenv(VERTEX_LOCATION_ENV_VAR):
        kwargs["vertex_location"] = location
    return kwargs


def complete(spec: ModelSpec, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
    """Run a chat completion.

    Args:
        spec: Resolved model.
        messages: Chat messages in OpenAI format.
        **kwargs: Any litellm completion parameter (``n``, ``temperature``,
            ``reasoning_effort``, ``response_format``, ...). Parameters the model
            does not support are dropped by litellm.

    Returns:
        A litellm ``ModelResponse``, which is OpenAI-shaped.
    """
    litellm = _configure()
    return litellm.completion(
        model=str(spec),
        messages=messages,
        timeout=REQUEST_TIMEOUT_S,
        **_provider_kwargs(spec),
        **kwargs,
    )


def embed(spec: ModelSpec, inputs: list[str], **kwargs: Any) -> Any:
    """Compute embeddings.

    Args:
        spec: Resolved embedding model.
        inputs: Texts to embed.
        **kwargs: Any litellm embedding parameter (``dimensions``, ...).

    Returns:
        A litellm ``EmbeddingResponse``.
    """
    litellm = _configure()
    return litellm.embedding(
        model=str(spec),
        input=inputs,
        **_provider_kwargs(spec),
        **kwargs,
    )
