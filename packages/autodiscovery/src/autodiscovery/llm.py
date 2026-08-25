"""The single transport for every model call in this package.

All chat, vision and embedding traffic goes through ``litellm``, which owns
provider routing, auth, request/response shaping and retries. Nothing here
speaks a provider's wire protocol directly, so adding a provider is a matter of
naming it in a model flag rather than writing a client.

Models are identified by litellm's ``<provider>/<model>`` string everywhere --
plain strings, not a wrapper type, because that string is already the canonical
identity and litellm takes it directly. The prefix is required: a bare name is
ambiguous (``claude-haiku-4.5`` is Anthropic direct or Copilot depending on who
you ask) and resolving one means calling ``litellm.get_llm_provider()``, which
runs GitHub's device-flow auth for Copilot models. This module only ever reads
litellm's static registry, via ``get_model_info(custom_llm_provider=...)``, which
is offline and auth-free.

Only three model facts are computed here rather than read from litellm, because
its registry cannot express them; each is noted at its definition. Everything
else -- which parameters a model accepts, wire formats, credentials -- is
litellm's job.

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

# litellm provider slugs this package has credentials and defaults for.
OPENAI = "openai"
VERTEX_AI = "vertex_ai"
GITHUB_COPILOT = "github_copilot"
SUPPORTED_PROVIDERS = (OPENAI, VERTEX_AI, GITHUB_COPILOT)

#: Providers whose litellm catalog is a complete, closed enumeration. For these,
#: a model missing from the registry really is unavailable, so it is an error
#: rather than a warning. OpenAI and Vertex ship models faster than litellm maps
#: them, so an unmapped model there is only a warning.
_CLOSED_CATALOG_PROVIDERS = frozenset({GITHUB_COPILOT})

VERTEX_PROJECT_ENV_VAR = "VERTEX_PROJECT_ID"
VERTEX_LOCATION_ENV_VAR = "VERTEX_LOCATION"

#: Per-request timeout, matching the previous AG2/OpenAI client default.
REQUEST_TIMEOUT_S = 600


class ModelError(ValueError):
    """Raised when a model name is unusable, or unusable for a given role."""


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


@functools.cache
def provider_of(model: str) -> str:
    """Return the litellm provider slug from a ``<provider>/<model>`` name.

    Args:
        model: A litellm-qualified model name.

    Returns:
        The provider slug.

    Raises:
        ModelError: If the name is unqualified, the prefix is not a litellm
            provider, or this package has no credentials for that provider.
    """
    if not model or not model.strip():
        raise ModelError("Model name must not be empty")

    provider, sep, remainder = model.strip().partition("/")
    if not sep or not remainder:
        raise ModelError(
            f"'{model}' is missing a provider. Model names are litellm-qualified as "
            f"<provider>/<model>, e.g. vertex_ai/{model} or openai/{model}."
        )

    from litellm.types.utils import LlmProviders

    if provider not in {member.value for member in LlmProviders}:
        raise ModelError(
            f"'{provider}' in '{model}' is not a litellm provider. Use one of "
            f"{', '.join(SUPPORTED_PROVIDERS)}."
        )
    if provider not in SUPPORTED_PROVIDERS:
        raise ModelError(
            f"'{model}' names litellm provider '{provider}', which autodiscovery has "
            f"no credentials for. Supported: {', '.join(SUPPORTED_PROVIDERS)}."
        )
    return provider


@functools.cache
def model_info(model: str) -> dict[str, Any] | None:
    """Look up a model in litellm's static registry, or None if unmapped.

    Passing ``custom_llm_provider`` explicitly keeps this offline and, for
    ``github_copilot``, avoids litellm's blocking device-flow auth.

    Args:
        model: A litellm-qualified model name.

    Returns:
        The registry entry, or None when litellm has not mapped the model.
    """
    provider = provider_of(model)
    bare = model.split("/", 1)[1]
    try:
        return dict(_configure().get_model_info(model=bare, custom_llm_provider=provider))
    except Exception:
        # Unmapped model. Preview models routinely ship before litellm maps
        # them, so this is a soft miss, not an error.
        return None


def accepts_temperature(model: str) -> bool:
    """Whether the model accepts a ``temperature`` parameter.

    Not answerable from litellm: ``get_supported_openai_params`` lists
    ``temperature`` for ``o4-mini``, which rejects it at the API, so
    ``drop_params`` will not strip it. OpenAI's reasoning models reject it;
    Gemini's reasoning models accept it.

    Args:
        model: A litellm-qualified model name.

    Returns:
        True when a temperature may be sent.
    """
    if provider_of(model) != OPENAI:
        return True
    info = model_info(model)
    return not (info and info.get("supports_reasoning"))


def max_n(model: str) -> int | None:
    """Return the max ``n`` per chat-completion request, or None if uncapped.

    Not answerable from litellm: its registry has no field for a provider's
    per-request sample cap.

    Args:
        model: A litellm-qualified model name.

    Returns:
        The cap, or None.
    """
    provider = provider_of(model)
    if provider == VERTEX_AI:
        return 5
    info = model_info(model)
    if provider == OPENAI and info and info.get("supports_reasoning"):
        return 8
    return None


def normalize_reasoning_effort(model: str, reasoning_effort: str | None) -> str | None:
    """Map a reasoning effort onto something the model accepts.

    Only ``minimal`` needs handling, and only for OpenAI: litellm records
    ``supports_minimal_reasoning_effort`` for the gpt-5 family but says nothing
    for the o-series, and a missing value means "unknown" rather than
    "unsupported" -- so it is treated as a positive signal only.

    Args:
        model: A litellm-qualified model name.
        reasoning_effort: The requested effort, or None.

    Returns:
        A provider-compatible effort value, or None.
    """
    if reasoning_effort != "minimal" or provider_of(model) != OPENAI:
        return reasoning_effort
    info = model_info(model)
    if not (info and info.get("supports_reasoning")):
        return reasoning_effort
    if info.get("supports_minimal_reasoning_effort"):
        return reasoning_effort
    print(f"[llm] model={model} does not support reasoning_effort='minimal'; using 'low' instead.")
    return "low"


def validate(
    model: str,
    *,
    flag: str,
    mode: str = "chat",
    require_vision: bool = False,
) -> None:
    """Check a model flag against litellm's registry before any model call.

    Unmapped models are a warning rather than an error for open-catalog
    providers: they ship models before litellm maps them, and a run must not be
    blocked on that. Checks only fire when litellm actually knows the model.

    Args:
        model: A litellm-qualified model name.
        flag: CLI flag name, used in messages.
        mode: Expected litellm mode, ``chat`` or ``embedding``.
        require_vision: Whether the model must accept image input.

    Raises:
        ModelError: If the model cannot serve its role.
    """
    provider = provider_of(model)
    info = model_info(model)

    if info is None:
        if provider in _CLOSED_CATALOG_PROVIDERS:
            catalog = _configure().models_by_provider.get(provider, [])
            available = sorted(name.removeprefix(f"{provider}/") for name in catalog)
            raise ModelError(
                f"{flag}={model} is not in {provider}'s catalog. Available: {', '.join(available)}"
            )
        print(
            f"[llm] {flag}={model} is not in litellm's model registry; skipping capability checks."
        )
        return

    if info.get("mode") != mode:
        raise ModelError(
            f"{flag}={model} is a '{info.get('mode')}' model, but a '{mode}' model is required."
        )
    if require_vision and not info.get("supports_vision"):
        raise ModelError(
            f"{flag}={model} does not support image input. Choose a vision-capable "
            f"model for plot analysis."
        )


def _provider_kwargs(model: str) -> dict[str, Any]:
    """Return provider-scoped kwargs for a litellm call."""
    if provider_of(model) != VERTEX_AI:
        return {}
    kwargs: dict[str, Any] = {}
    # Map this package's long-standing env vars onto litellm's parameter names
    # so existing deployment configuration keeps working unchanged.
    if project := os.getenv(VERTEX_PROJECT_ENV_VAR):
        kwargs["vertex_project"] = project
    if location := os.getenv(VERTEX_LOCATION_ENV_VAR):
        kwargs["vertex_location"] = location
    return kwargs


def complete(model: str, messages: list[dict[str, Any]], **kwargs: Any) -> Any:
    """Run a chat completion.

    Args:
        model: A litellm-qualified model name.
        messages: Chat messages in OpenAI format.
        **kwargs: Any litellm completion parameter (``n``, ``temperature``,
            ``reasoning_effort``, ``response_format``, ...). Parameters the model
            does not support are dropped by litellm.

    Returns:
        A litellm ``ModelResponse``, which is OpenAI-shaped.
    """
    return _configure().completion(
        model=model,
        messages=messages,
        timeout=REQUEST_TIMEOUT_S,
        **_provider_kwargs(model),
        **kwargs,
    )


def embed(model: str, inputs: list[str], **kwargs: Any) -> Any:
    """Compute embeddings.

    Args:
        model: A litellm-qualified embedding model name.
        inputs: Texts to embed.
        **kwargs: Any litellm embedding parameter (``dimensions``, ...).

    Returns:
        A litellm ``EmbeddingResponse``.
    """
    return _configure().embedding(
        model=model,
        input=inputs,
        **_provider_kwargs(model),
        **kwargs,
    )
