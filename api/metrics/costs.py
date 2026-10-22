"""LLM cost calculation for metrics dashboard."""

from __future__ import annotations

from datetime import UTC, datetime

# Pricing per 1M tokens (USD) — Vertex AI standard pricing
# Source: https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing
LLM_PRICING: dict[str, dict[str, float]] = {
    # Google Gemini models
    "gemini-3.8-flash": {"input": 1.50, "output": 7.50},
    "gemini-3.5-flash": {"input": 1.50, "output": 9.00},
    "gemini-3.7-flash": {"input": 1.50, "output": 7.50},
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3-pro-preview": {"input": 2.00, "output": 12.00},
    "gemini-3-flash-preview": {"input": 0.50, "output": 3.00},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.5-pro-preview-05-06": {"input": 1.25, "output": 10.00},
    "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
    "gemini-2.5-flash-preview-04-17": {"input": 0.30, "output": 2.50},
    "gemini-2.0-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash-001": {"input": 0.15, "output": 0.60},
    # OpenAI models
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-2024-08-06": {"input": 2.50, "output": 10.00},
    "gpt-5-mini": {"input": 0.40, "output": 1.60},
    "o4-mini": {"input": 1.10, "output": 4.40},
    "o4-mini-2025-04-16": {"input": 1.10, "output": 4.40},
    "o3-mini": {"input": 1.10, "output": 4.40},
}

# Fallback pricing for unknown models (conservative: uses gemini-3.1-pro rates)
_FALLBACK_PRICING = {"input": 2.00, "output": 12.00}

# Global standard estimates, net of Google's 50% promotional credits through 2026.
_FLASH_PROMO_END = datetime(2027, 1, 1, tzinfo=UTC)
_FLASH_PROMO_MODELS = frozenset({"gemini-3.7-flash", "gemini-3.8-flash"})
_FLASH_PROMO_PRICING = {"input": 0.75, "output": 3.75}


def _parse_usage_time(usage_at: str | None) -> datetime | None:
    """Parse a usage timestamp as UTC; missing and invalid values are unknown."""
    try:
        when = datetime.fromisoformat(usage_at) if usage_at else None
    except (ValueError, TypeError):
        return None
    if when is None:
        return None
    return when.replace(tzinfo=UTC) if when.tzinfo is None else when.astimezone(UTC)


def _lookup_pricing(model_name: str, *, usage_at: str | None = None) -> dict[str, float]:
    """Look up global standard pricing at an ISO timestamp, stripping provider prefixes.

    Missing or invalid timestamps use standard, non-promotional rates so estimates
    never depend on scan time. Naive timestamps are UTC.
    """
    pricing_key = model_name if model_name in LLM_PRICING else model_name.rsplit("/", 1)[-1]
    if pricing_key in _FLASH_PROMO_MODELS:
        when = _parse_usage_time(usage_at)
        if when is not None and when < _FLASH_PROMO_END:
            return _FLASH_PROMO_PRICING

    return LLM_PRICING.get(pricing_key, _FALLBACK_PRICING)


def calculate_llm_cost(
    usage_summary: dict, *, usage_at: str | None = None
) -> tuple[float, dict[str, float]]:
    """Calculate LLM cost from a usage summary.

    Args:
        usage_summary: The llm_usage_summary.json data with by_model breakdown.
        usage_at: Resolved run timestamp for historical pricing. All usage in a run
            is estimated at this rate, including runs spanning a price change.

    Returns:
        Tuple of (total_cost_usd, {model_name: cost_usd}).
    """
    by_model = usage_summary.get("by_model", {})
    total_cost = 0.0
    cost_by_model: dict[str, float] = {}

    for model_name, usage in by_model.items():
        pricing = _lookup_pricing(model_name, usage_at=usage_at)
        prompt_tokens = usage.get("prompt_tokens", 0)
        total_tokens = usage.get("total_tokens", 0)
        # Use total - prompt to capture all output tokens including reasoning
        output_tokens = max(0, total_tokens - prompt_tokens)
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        model_cost = input_cost + output_cost
        cost_by_model[model_name] = round(model_cost, 6)
        total_cost += model_cost

    return round(total_cost, 6), cost_by_model


def get_duration_seconds(created_at: str | None, finished_at: str | None) -> float | None:
    """Calculate duration in seconds between two ISO timestamps."""
    if not created_at or not finished_at:
        return None
    try:
        start = datetime.fromisoformat(created_at)
        end = datetime.fromisoformat(finished_at)
        return max(0.0, (end - start).total_seconds())
    except (ValueError, TypeError):
        return None
