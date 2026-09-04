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

Any of litellm's providers can be named; supplying credentials for one is the
operator's job and follows litellm's own env-var conventions. The three this
package documents and tests:

- ``vertex_ai`` uses Application Default Credentials. Set
  ``GOOGLE_APPLICATION_CREDENTIALS`` to a service-account key, or run
  ``gcloud auth application-default login`` locally. ``VERTEX_PROJECT_ID`` and
  ``VERTEX_LOCATION`` are mapped onto litellm's ``vertex_project`` /
  ``vertex_location`` so existing deployment env vars keep working.
- ``openai`` uses ``OPENAI_API_KEY``.
- ``github_copilot`` caches a GitHub OAuth token at
  ``$GITHUB_COPILOT_TOKEN_DIR/access-token`` (default
  ``~/.config/litellm/github_copilot``). litellm obtains it via device-code login
  on first use, which works interactively but has no TTY detection -- a headless
  run without a cached token blocks on a device prompt. Pre-seed the file for
  non-interactive use. See ``docs/autodiscovery/standalone.md``.
"""

from __future__ import annotations

import functools
import os
from typing import Any

from autodiscovery.llm_retry import call_with_backoff

# Providers this package has special handling for. Any litellm provider works;
# these are the ones with a documented credential path or a quirk below.
OPENAI = "openai"
VERTEX_AI = "vertex_ai"
GITHUB_COPILOT = "github_copilot"

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

    # Retries are ours, via call_with_backoff below. litellm's num_retries maps
    # onto the provider SDK's max_retries, which ignores our documented
    # LLM_RETRY_INITIAL_DELAY_SECONDS / LLM_RETRY_MAX_DELAY_SECONDS. Setting it
    # to 0 keeps a single retry layer rather than two nested ones.
    litellm.num_retries = 0
    return litellm


@functools.cache
def provider_of(model: str) -> str:
    """Return the litellm provider slug from a ``<provider>/<model>`` name.

    Args:
        model: A litellm-qualified model name.

    Returns:
        The provider slug.

    Raises:
        ModelError: If the name is unqualified or the prefix is not one of
            litellm's provider slugs.
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

    # Any of litellm's ~149 providers is allowed; supplying its credentials is
    # the operator's job, per litellm's own env-var conventions. Checking the
    # slug here only turns a typo into a startup error instead of a confusing
    # auth failure on the first model call.
    if provider not in {member.value for member in LlmProviders}:
        raise ModelError(
            f"'{provider}' in '{model}' is not a litellm provider. See "
            f"https://docs.litellm.ai/docs/providers for the full list."
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
    if provider == GITHUB_COPILOT:
        # Measured: n=10 fails with "Invalid 'n': ... Expected a value <= 8".
        # Without this, anything above 8 errors instead of batching -- notably
        # dedupe, which asks for 10 merge votes.
        return 8
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


@functools.cache
def _copilot_live_catalog() -> dict[str, dict[str, Any]] | None:
    """Return the Copilot models this account can actually call, or None.

    litellm's static ``github_copilot`` catalog is not authoritative: it lists
    models an account cannot call (``gpt-5`` returns "The requested model is not
    supported") and omits ones it can (``gpt-5.4``, ``claude-sonnet-5``).
    Copilot's own ``/models`` endpoint is closer to the truth, and it also
    reports vision support per model.

    It is still only a superset of what chat completions will serve: some listed
    models return ``model_not_supported`` anyway (``gpt-5.5``, ``claude-opus-5``
    on a plan that lists both). Nothing in the payload distinguishes them --
    entries for a working and a refused model are structurally identical, and it
    is not a stale-client-header issue either. So this narrows the failure window
    rather than closing it; a model absent from the list definitely will not
    work, but presence is not a guarantee.

    This deliberately reads only litellm's *cached, unexpired* API key. It never
    touches ``Authenticator``, so it cannot trigger the device-flow login that
    would block a non-interactive run. If there is no usable cached key, or the
    request fails, it returns None and the caller falls back to the registry.

    Returns:
        Mapping of model id to its ``/models`` entry, or None if unavailable.
    """
    import json

    key_dir = os.getenv(
        "GITHUB_COPILOT_TOKEN_DIR", os.path.expanduser("~/.config/litellm/github_copilot")
    )
    key_file = os.path.join(key_dir, os.getenv("GITHUB_COPILOT_API_KEY_FILE", "api-key.json"))
    try:
        import time

        import httpx

        with open(key_file) as handle:
            cached = json.load(handle)
        if cached.get("expires_at", 0) <= time.time():
            return None
        api_base = (cached.get("endpoints") or {}).get("api")
        token = cached.get("token")
        if not api_base or not token:
            return None
        response = httpx.get(
            f"{api_base}/models",
            headers={
                "Authorization": f"Bearer {token}",
                "Copilot-Integration-Id": "vscode-chat",
                "Editor-Version": "vscode/1.85.0",
            },
            timeout=15,
        )
        response.raise_for_status()
        return {entry["id"]: entry for entry in response.json().get("data", []) if entry.get("id")}
    except Exception:
        return None


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

    # Copilot's own endpoint knows what this account can call; litellm's static
    # catalog does not. Prefer it whenever we can read it without authenticating.
    if provider == GITHUB_COPILOT and (live := _copilot_live_catalog()) is not None:
        bare = model.split("/", 1)[1]
        if bare not in live:
            raise ModelError(
                f"{flag}={model} is not available to this Copilot account. "
                f"Available: {', '.join(sorted(live))}"
            )
        supports = (live[bare].get("capabilities") or {}).get("supports") or {}
        if require_vision and not supports.get("vision"):
            raise ModelError(
                f"{flag}={model} does not support image input. Choose a vision-capable "
                f"model for plot analysis."
            )

    info = model_info(model)
    if info is None:
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


def reported_cost(response: Any) -> float | None:
    """Return the cost litellm computed for a response, if it computed one.

    This is the only place ``_hidden_params`` is read. litellm sets
    ``response_cost`` on every response it returns, derived from its own
    maintained per-model prices.

    Args:
        response: A litellm response object.

    Returns:
        The cost in USD, or None when litellm did not price the call.
    """
    hidden = getattr(response, "_hidden_params", None)
    if not isinstance(hidden, dict):
        return None
    try:
        cost = hidden.get("response_cost")
        return None if cost is None else float(cost)
    except (TypeError, ValueError):
        return None


def cost_of(response: Any, model: str) -> dict[str, float] | None:
    """Return litellm's cost for one response, split by token type.

    litellm computes the cost of every call it makes and hangs it on the
    response as ``_hidden_params["response_cost"]``; that figure is
    authoritative here and is never recomputed. The prompt/completion split is
    not on the response, so it comes from ``litellm.cost_per_token`` and is then
    scaled onto the authoritative total -- ``response_cost`` also covers cache
    reads, image input and built-in tools, which a plain prompt/completion split
    does not, so the two disagree on some calls and the total is the one to keep.

    None means the cost is *unknown*, which is the honest answer for a model
    litellm has no prices for and is not the same as a cost of zero. Two cases
    reach it: a model litellm has not mapped yet, which preview models routinely
    are, and a provider that does not bill per token at all -- ``github_copilot``
    bills "premium requests", and litellm reports every one of its models at a
    zero token price, so a per-token figure for it would be fiction.

    Args:
        response: A litellm ``ModelResponse`` or ``EmbeddingResponse``.
        model: The litellm-qualified model name the request was made with.

    Returns:
        Mapping with ``total_usd`` and, when the split is derivable,
        ``prompt_usd``, ``completion_usd`` and ``reasoning_usd`` -- which sum to
        ``total_usd`` up to float precision. None when the model cannot be priced.
    """
    total = reported_cost(response)
    usage = getattr(response, "usage", None)
    prompt_tokens = _usage_int(usage, "prompt_tokens")
    completion_tokens = _usage_int(usage, "completion_tokens")
    # Reasoning tokens are a subset of completion_tokens in the OpenAI usage
    # shape litellm normalizes to, not an addition to them.
    reasoning_tokens = min(
        completion_tokens,
        _usage_int(_usage_get(usage, "completion_tokens_details"), "reasoning_tokens"),
    )

    try:
        prompt_usd, completion_usd = _configure().cost_per_token(
            model=model.split("/", 1)[1],
            custom_llm_provider=provider_of(model),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    except Exception:
        # litellm has not mapped the model, so it has no prices for it.
        return None
    split_total = float(prompt_usd) + float(completion_usd)
    if total is None:
        total = split_total

    if total <= 0:
        # A priced call over a non-empty prompt always costs something, so zero
        # here means an unpriced model rather than a free one.
        return None if prompt_tokens + completion_tokens > 0 else {"total_usd": 0.0}
    if split_total <= 0:
        return {"total_usd": total}

    scale = total / split_total
    prompt_usd = float(prompt_usd) * scale
    completion_usd = float(completion_usd) * scale
    # Reasoning tokens bill at the output rate, so reporting them separately is
    # a share of the completion cost rather than a price of their own.
    reasoning_usd = (
        completion_usd * (reasoning_tokens / completion_tokens) if completion_tokens else 0.0
    )
    return {
        "total_usd": total,
        "prompt_usd": prompt_usd,
        "completion_usd": completion_usd - reasoning_usd,
        "reasoning_usd": reasoning_usd,
    }


def _usage_get(usage: Any, key: str) -> Any:
    """Read a field off a usage payload, dict-like or object-like."""
    if isinstance(usage, dict):
        return usage.get(key)
    return getattr(usage, key, None)


def _usage_int(usage: Any, key: str) -> int:
    """Read a non-negative token count off a usage payload, dict-like or not."""
    value = _usage_get(usage, key)
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


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
    litellm = _configure()
    return call_with_backoff(
        lambda: litellm.completion(
            model=model,
            messages=messages,
            timeout=REQUEST_TIMEOUT_S,
            **_provider_kwargs(model),
            **kwargs,
        ),
        label=f"completion(model={model})",
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
    litellm = _configure()
    return call_with_backoff(
        lambda: litellm.embedding(
            model=model,
            input=inputs,
            **_provider_kwargs(model),
            **kwargs,
        ),
        label=f"embedding(model={model})",
    )
