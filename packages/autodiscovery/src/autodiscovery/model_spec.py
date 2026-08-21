"""Provider/model resolution built on litellm's naming convention and registry.

Every user-facing model flag (``--model``, ``--belief_model``, ``--vision_model``,
``--embedding_model``) accepts litellm's ``<provider>/<model>`` form, where the
provider is one of litellm's snake_case slugs (``openai``, ``vertex_ai``,
``gemini``, ``github_copilot``, ...). Bare model names keep working: litellm
resolves ``o4-mini`` to ``openai`` and ``gemini-3.1-pro-preview`` to
``vertex_ai`` on its own, so existing deployment configs are unaffected.

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

#: Prefixes accepted at the CLI boundary that are not litellm provider slugs.
#: ``google/`` is Vertex's OpenAI-compatible wire format, which leaked into
#: user-facing model names before this module existed. ``copilot`` is the value
#: of the deprecated ``--llm_provider``/``--embedding_provider`` flags.
_PROVIDER_ALIASES = {
    "google": VERTEX_AI,
    "copilot": GITHUB_COPILOT,
}

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
    def wire_model_name(self) -> str:
        """Return the model name this provider's transport expects on the wire.

        Vertex's OpenAI-compatible endpoint requires a publisher prefix
        (``google/gemini-...``). That is a transport detail, so it is applied
        here rather than carried through user-facing config.
        """
        if self.is_vertex:
            return f"google/{self.model}"
        return self.model

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
        """Whether the model takes a ``reasoning_effort`` parameter.

        litellm's registry has no reasoning data for ``github_copilot`` models
        even where the underlying model reasons, so Copilot keeps passing the
        caller's value through to its SDK.
        """
        if self.is_copilot:
            return True
        info = self.info
        return bool(info.get("supports_reasoning")) if info else False

    @property
    def accepts_temperature(self) -> bool:
        """Whether the model accepts a ``temperature`` parameter.

        OpenAI's reasoning models reject it; Gemini reasoning models accept it.
        """
        return not (self.is_openai and self.supports_reasoning)

    @property
    def max_n(self) -> int | None:
        """Return the max ``n`` per request, or None when uncapped."""
        if self.is_openai and self.supports_reasoning:
            return 8
        return _MAX_N_BY_PROVIDER.get(self.provider)


def canonical_provider(name: str) -> str:
    """Return the litellm slug for a provider name, resolving legacy aliases."""
    return _PROVIDER_ALIASES.get(name, name)


def parse_model(spec: str, *, default_provider: str | None = None) -> ModelSpec:
    """Resolve a model flag to a provider and bare model name.

    Args:
        spec: ``<provider>/<model>`` or a bare model name.
        default_provider: Provider to assume for a bare model name, from the
            deprecated ``--llm_provider``/``--embedding_provider`` flags. When
            omitted, litellm resolves the bare name itself.

    Returns:
        The resolved :class:`ModelSpec`.

    Raises:
        ModelSpecError: If the prefix is not a litellm provider, the provider
            has no transport here, or a bare name cannot be resolved.
    """
    if not spec or not spec.strip():
        raise ModelSpecError("Model name must not be empty")
    spec = spec.strip()

    prefix, sep, remainder = spec.partition("/")
    if sep and remainder:
        provider = canonical_provider(prefix)
        if provider not in _provider_slugs():
            raise ModelSpecError(
                f"'{prefix}' in '{spec}' is not a litellm provider. Use one of "
                f"{', '.join(SUPPORTED_PROVIDERS)}, or a bare model name."
            )
        return _checked(ModelSpec(provider=provider, model=remainder), spec)

    if default_provider is not None:
        provider = canonical_provider(default_provider)
        return _checked(ModelSpec(provider=provider, model=spec), spec)

    try:
        model, provider, *_ = _litellm().get_llm_provider(spec)
    except Exception:
        return _checked(ModelSpec(provider=_legacy_provider(spec), model=spec), spec)
    return _checked(ModelSpec(provider=provider, model=model), spec)


def _legacy_provider(spec: str) -> str:
    """Route a bare name litellm cannot resolve, the way this package used to.

    litellm only resolves bare names it has in its registry, so a model released
    after the pinned litellm version -- ``gemini-3.2-pro-preview``, say -- fails
    lookup even though the run would work. Falling back to the pre-litellm
    heuristic (``gemini*`` to Vertex, everything else to OpenAI) keeps existing
    deployment configs working. This is the one name-prefix test left in the
    codebase, and qualifying the flag as ``<provider>/<model>`` skips it.
    """
    provider = VERTEX_AI if spec.split("/")[-1].startswith("gemini") else OPENAI
    print(
        f"[model_spec] '{spec}' is not in litellm's model registry; routing to "
        f"'{provider}' by name. Qualify it as '{provider}/{spec}' to make this explicit."
    )
    return provider


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
    default_provider: str | None = None,
    mode: str = "chat",
    require_vision: bool = False,
) -> ModelSpec:
    """Resolve a model flag and check it against litellm's registry.

    Unmapped models are a warning rather than an error: preview models regularly
    ship before litellm's registry catches up, and a run must not be blocked on
    that. Checks only fire when litellm actually knows the model.

    Args:
        spec: ``<provider>/<model>`` or a bare model name.
        flag: CLI flag name, used in messages.
        default_provider: Provider to assume for a bare model name.
        mode: Expected litellm mode, ``chat`` or ``embedding``.
        require_vision: Whether the model must accept image input.

    Returns:
        The resolved :class:`ModelSpec`.

    Raises:
        ModelSpecError: If the model is unusable for its role.
    """
    resolved = parse_model(spec, default_provider=default_provider)
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
