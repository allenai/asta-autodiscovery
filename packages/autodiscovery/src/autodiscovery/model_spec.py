"""Provider/model resolution built on litellm's naming convention and registry.

Every user-facing model flag (``--model``, ``--belief_model``, ``--vision_model``,
``--embedding_model``) takes litellm's ``<provider>/<model>`` form, where the
provider is one of litellm's snake_case slugs (``openai``, ``vertex_ai``,
``gemini``, ``github_copilot``, ...). The prefix is required: a bare name is
ambiguous (``claude-haiku-4.5`` is Anthropic direct or Copilot depending on who
you ask) and resolving one means asking litellm, which authenticates.

This module is the single place that answers "which provider, and what can this
model do". Call sites branch on :class:`ModelSpec` fields instead of sniffing
model-name prefixes.

Note on litellm and Copilot: ``litellm.get_llm_provider()`` (and the
``litellm.supports_*`` helpers, which call it) run GitHub's device-flow auth when
handed a ``github_copilot/`` model, printing a device code and blocking for three
60s attempts. litellm has no env var to disable that -- its
``GITHUB_COPILOT_*`` variables only relocate the token files and endpoints -- so
it would hang any non-interactive deployment. This module therefore splits the
provider prefix itself and only ever queries litellm's static registry via
``get_model_info(model=..., custom_llm_provider=...)``, which is offline and
auth-free. ``test_resolution_never_triggers_copilot_device_flow`` guards this.

litellm is used here as the naming, registry, and validation authority; the
actual transports (Vertex's OpenAI-compatible endpoint, the Copilot CLI SDK,
OpenAI direct) are unchanged.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Any

# litellm provider slugs this package has transports for.
OPENAI = "openai"
VERTEX_AI = "vertex_ai"
GITHUB_COPILOT = "github_copilot"

#: Providers whose transport is implemented in this package.
SUPPORTED_PROVIDERS = (OPENAI, VERTEX_AI, GITHUB_COPILOT)

#: Providers whose litellm catalog is a complete, closed enumeration. For these,
#: a model missing from the registry really is unavailable, so it is an error
#: rather than a warning. OpenAI and Vertex ship models faster than litellm maps
#: them, so an unmapped model there is only a warning.
_CLOSED_CATALOG_PROVIDERS = frozenset({GITHUB_COPILOT})

#: Max ``n`` per chat-completion request, by provider. litellm's registry does
#: not model this, so it stays an explicit table rather than a name prefix test.
_MAX_N_BY_PROVIDER = {VERTEX_AI: 5}


class ModelSpecError(ValueError):
    """Raised when a model flag names an unusable provider or model."""


@functools.cache
def _litellm() -> Any:
    """Import litellm lazily; importing it costs seconds."""
    import litellm

    # litellm prints a provider-list banner on every resolution failure. We
    # surface our own errors, so silence it.
    litellm.suppress_debug_info = True
    return litellm


@functools.cache
def _provider_slugs() -> frozenset[str]:
    """Return litellm's full set of provider slugs."""
    from litellm.types.utils import LlmProviders

    return frozenset(provider.value for provider in LlmProviders)


@functools.cache
def _model_info(provider: str, model: str) -> dict[str, Any] | None:
    """Look up a model in litellm's static registry, or None if unmapped.

    Never calls ``get_llm_provider()``: passing ``custom_llm_provider``
    explicitly keeps this offline and, for ``github_copilot``, avoids litellm's
    blocking device-flow auth.
    """
    try:
        return dict(_litellm().get_model_info(model=model, custom_llm_provider=provider))
    except Exception:
        # Unmapped model. Preview models routinely ship before litellm maps
        # them, so this is a soft miss, not an error.
        return None


@dataclass(frozen=True)
class ModelSpec:
    """A model flag resolved to a litellm provider plus a bare model name."""

    provider: str
    model: str

    def __str__(self) -> str:
        """Return the canonical litellm ``<provider>/<model>`` name."""
        return f"{self.provider}/{self.model}"

    @property
    def is_openai(self) -> bool:
        """Whether this model is served by OpenAI directly."""
        return self.provider == OPENAI

    @property
    def is_vertex(self) -> bool:
        """Whether this model is served by Vertex AI."""
        return self.provider == VERTEX_AI

    @property
    def is_copilot(self) -> bool:
        """Whether this model is served by the GitHub Copilot CLI."""
        return self.provider == GITHUB_COPILOT

    @property
    def info(self) -> dict[str, Any] | None:
        """Return litellm's registry entry for this model, or None if unmapped."""
        return _model_info(self.provider, self.model)

    @property
    def supports_vision(self) -> bool | None:
        """Whether the model accepts image input; None when unmapped."""
        info = self.info
        if info is None:
            return None
        return bool(info.get("supports_vision"))

    @property
    def supports_reasoning(self) -> bool:
        """Whether litellm's registry records reasoning support.

        litellm drops ``reasoning_effort`` for models that do not accept it, so
        this is only consulted for the two rules litellm cannot express:
        :attr:`accepts_temperature` and minimal-effort normalization.
        """
        info = self.info
        return bool(info.get("supports_reasoning")) if info else False

    @property
    def supports_minimal_reasoning_effort(self) -> bool:
        """Whether litellm affirmatively records support for ``minimal`` effort.

        The registry only ever says ``True`` or nothing, so a missing value means
        "unknown", not "unsupported". Callers must treat it as a positive signal
        only.
        """
        info = self.info
        return bool(info.get("supports_minimal_reasoning_effort")) if info else False

    @property
    def accepts_temperature(self) -> bool:
        """Whether the model accepts a ``temperature`` parameter.

        OpenAI's reasoning models reject it; Gemini reasoning models accept it.
        litellm cannot answer this: ``supported_openai_params`` lists
        ``temperature`` for ``o4-mini``, which rejects it at the API.
        """
        return not (self.is_openai and self.supports_reasoning)

    @property
    def max_n(self) -> int | None:
        """Return the max ``n`` per request, or None when uncapped."""
        if self.is_openai and self.supports_reasoning:
            return 8
        return _MAX_N_BY_PROVIDER.get(self.provider)


def parse_model(spec: str) -> ModelSpec:
    """Resolve a litellm ``<provider>/<model>`` name.

    Args:
        spec: A litellm-qualified model name, e.g. ``vertex_ai/gemini-3-flash-preview``.

    Returns:
        The resolved :class:`ModelSpec`.

    Raises:
        ModelSpecError: If the name is unqualified, the prefix is not a litellm
            provider, or the provider has no transport here.
    """
    if not spec or not spec.strip():
        raise ModelSpecError("Model name must not be empty")
    spec = spec.strip()

    provider, sep, model = spec.partition("/")
    if not sep or not model:
        raise ModelSpecError(
            f"'{spec}' is missing a provider. Model names are litellm-qualified as "
            f"<provider>/<model>, e.g. vertex_ai/{spec} or openai/{spec}."
        )
    if provider not in _provider_slugs():
        raise ModelSpecError(
            f"'{provider}' in '{spec}' is not a litellm provider. Use one of "
            f"{', '.join(SUPPORTED_PROVIDERS)}."
        )
    return _checked(ModelSpec(provider=provider, model=model), spec)


def _checked(resolved: ModelSpec, spec: str) -> ModelSpec:
    """Reject providers this package has no transport for."""
    if resolved.provider not in SUPPORTED_PROVIDERS:
        raise ModelSpecError(
            f"'{spec}' resolves to litellm provider '{resolved.provider}', which "
            f"autodiscovery has no transport for. Supported: "
            f"{', '.join(SUPPORTED_PROVIDERS)}."
        )
    return resolved


def validate_model(
    spec: str,
    *,
    flag: str,
    mode: str = "chat",
    require_vision: bool = False,
) -> ModelSpec:
    """Resolve a model flag and check it against litellm's registry.

    Unmapped models are a warning rather than an error: preview models regularly
    ship before litellm's registry catches up, and a run must not be blocked on
    that. Checks only fire when litellm actually knows the model.

    Args:
        spec: A litellm-qualified ``<provider>/<model>`` name.
        flag: CLI flag name, used in messages.
        mode: Expected litellm mode, ``chat`` or ``embedding``.
        require_vision: Whether the model must accept image input.

    Returns:
        The resolved :class:`ModelSpec`.

    Raises:
        ModelSpecError: If the model is unusable for its role.
    """
    resolved = parse_model(spec)
    info = resolved.info

    if info is None:
        if resolved.provider in _CLOSED_CATALOG_PROVIDERS:
            catalog = _litellm().models_by_provider.get(resolved.provider, [])
            available = sorted(name.removeprefix(f"{resolved.provider}/") for name in catalog)
            raise ModelSpecError(
                f"{flag}={spec} is not in {resolved.provider}'s catalog. "
                f"Available: {', '.join(available)}"
            )
        print(
            f"[model_spec] {flag}={spec} resolves to provider "
            f"'{resolved.provider}' but is not in litellm's model registry; "
            "skipping capability checks."
        )
        return resolved

    if info.get("mode") != mode:
        raise ModelSpecError(
            f"{flag}={spec} is a '{info.get('mode')}' model, but a '{mode}' model is required."
        )

    if require_vision and not resolved.supports_vision:
        raise ModelSpecError(
            f"{flag}={spec} does not support image input. Choose a vision-capable "
            f"model for plot analysis."
        )

    return resolved
