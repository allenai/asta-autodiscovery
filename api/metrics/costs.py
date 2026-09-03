"""LLM cost reporting for the metrics dashboard.

Cost is computed where the calls are made, not here. litellm prices every call
from its own maintained per-model rate table and the run's ``UsageTracker``
records that number on each event, so this module only sums recorded dollars.
There is deliberately no price table and no fallback rate: a call litellm could
not price is reported as unavailable rather than approximated, and litellm is
not a dependency of this service.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def _coerce_float(value: Any) -> float:
    """Parse a value into a non-negative float, returning 0.0 on invalid input."""
    try:
        return max(0.0, float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def bucket_costs_by_type(bucket: Any) -> tuple[float, float, float]:
    """Return the recorded prompt/completion/reasoning costs for one bucket.

    Args:
        bucket: A ``by_model``/``by_agent``/... bucket from a usage summary.

    Returns:
        Tuple of (prompt_cost_usd, completion_cost_usd, reasoning_cost_usd).
        All zero for runs recorded before costs were tracked at the source.
    """
    if not isinstance(bucket, dict):
        return 0.0, 0.0, 0.0
    return (
        _coerce_float(bucket.get("prompt_cost_usd")),
        _coerce_float(bucket.get("completion_cost_usd")),
        _coerce_float(bucket.get("reasoning_cost_usd")),
    )


def has_cost_data(usage_summary: dict | None) -> bool:
    """Whether a usage summary carries costs recorded at the source.

    Runs completed before cost recording landed have usage summaries with no
    cost fields at all. Their cost is unknown, not zero, and the dashboard
    reports it as unavailable rather than mixing two costing methods.

    Args:
        usage_summary: The ``llm_usage_summary.json`` data, if any.

    Returns:
        True when at least one call in the summary was priced.
    """
    if not usage_summary:
        return False
    totals = usage_summary.get("totals")
    if isinstance(totals, dict) and "calls_with_cost" in totals:
        return int(totals.get("calls_with_cost") or 0) > 0
    # Summaries predating cost recording carry no cost fields whatsoever.
    return any(
        isinstance(bucket, dict) and "cost_usd" in bucket
        for bucket in (usage_summary.get("by_model") or {}).values()
    )


def calculate_llm_cost(usage_summary: dict) -> tuple[float, dict[str, float]]:
    """Sum the recorded LLM cost of a run.

    Args:
        usage_summary: The llm_usage_summary.json data with by_model breakdown.

    Returns:
        Tuple of (total_cost_usd, {model_name: cost_usd}). Both are zero/empty
        for runs with no recorded cost -- use :func:`has_cost_data` to tell that
        apart from a run that genuinely cost nothing.
    """
    by_model = usage_summary.get("by_model", {})
    total_cost = 0.0
    cost_by_model: dict[str, float] = {}

    for model_name, usage in by_model.items():
        model_cost = _coerce_float(usage.get("cost_usd")) if isinstance(usage, dict) else 0.0
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
