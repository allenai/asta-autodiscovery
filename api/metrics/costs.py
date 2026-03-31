"""LLM cost calculation for metrics dashboard."""

from __future__ import annotations

from datetime import datetime

# Pricing per 1M tokens (USD) — Vertex AI standard pricing
# Source: https://cloud.google.com/vertex-ai/generative-ai/pricing
LLM_PRICING: dict[str, dict[str, float]] = {
    # Google Gemini models
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


def _lookup_pricing(model_name: str) -> dict[str, float]:
    """Look up pricing for a model name, stripping provider prefixes."""
    if model_name in LLM_PRICING:
        return LLM_PRICING[model_name]

    # Strip provider prefix (e.g., "google/gemini-3.1-pro-preview" -> "gemini-3.1-pro-preview")
    stripped = model_name.split("/")[-1] if "/" in model_name else model_name
    if stripped in LLM_PRICING:
        return LLM_PRICING[stripped]

    return _FALLBACK_PRICING


def calculate_llm_cost(usage_summary: dict) -> tuple[float, dict[str, float]]:
    """Calculate LLM cost from a usage summary.

    Args:
        usage_summary: The llm_usage_summary.json data with by_model breakdown.

    Returns:
        Tuple of (total_cost_usd, {model_name: cost_usd}).
    """
    by_model = usage_summary.get("by_model", {})
    total_cost = 0.0
    cost_by_model: dict[str, float] = {}

    for model_name, usage in by_model.items():
        pricing = _lookup_pricing(model_name)
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
