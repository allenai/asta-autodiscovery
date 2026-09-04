"""LLM cost readout for the metrics dashboard.

Nothing here prices a model. The autodiscovery package records what litellm
charged for each call at the moment it makes it, into
``llm_usage_summary.json`` and ``llm_usage_events.jsonl``, so this module only
adds up a field. That keeps one costing method in play instead of two, and keeps
litellm -- a heavy dependency, pinned to a different Python than this service --
out of the API image.

Cost is genuinely unavailable for some runs, and this module reports that rather
than substituting zero:

- Runs that finished before cost recording landed carry no cost field at all.
  Their old figures came from a hand-maintained price table and were
  approximations; showing a gap beats silently mixing two costing methods.
- Some providers are not billed per token. ``github_copilot`` bills "premium
  requests", so litellm has no token price for it and no honest dollar figure
  exists for those calls.

:func:`cost_status` distinguishes the two from a fully-costed run, and the
dashboard renders each differently.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

#: No recorded call carried a cost.
UNAVAILABLE = "unavailable"
#: Some recorded calls carried a cost and some did not; the total is a lower bound.
PARTIAL = "partial"
#: Every recorded call carried a cost.
COMPLETE = "complete"


def coerce_int(value: Any) -> int:
    """Parse a value into a non-negative int, returning 0 on invalid input."""
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def coerce_float(value: Any) -> float:
    """Parse a value into a float, returning 0.0 on invalid input."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def bucket_call_counts(bucket: Any) -> tuple[int, int]:
    """Return (calls, calls that carried a cost) for one usage bucket.

    Args:
        bucket: A usage bucket from ``llm_usage_summary.json``.

    Returns:
        Tuple of total calls and the subset of them litellm priced.
    """
    if not isinstance(bucket, dict):
        return 0, 0
    return coerce_int(bucket.get("calls")), coerce_int(bucket.get("calls_with_cost"))


def bucket_costs(bucket: Any) -> tuple[float, float, float]:
    """Return one bucket's (prompt, completion, reasoning) recorded costs.

    The three parts sum to the bucket's total for calls recorded per response.
    They are all zero for calls recorded from AG2's running per-agent totals,
    which know the total but not its split -- so read the total from
    ``cost_usd`` rather than by adding these up.

    Args:
        bucket: A usage bucket from ``llm_usage_summary.json``.

    Returns:
        Tuple of prompt, completion and reasoning cost in USD.
    """
    if not isinstance(bucket, dict):
        return 0.0, 0.0, 0.0
    return (
        coerce_float(bucket.get("prompt_cost_usd")),
        coerce_float(bucket.get("completion_cost_usd")),
        coerce_float(bucket.get("reasoning_cost_usd")),
    )


def calculate_llm_cost(usage_summary: dict) -> tuple[float, dict[str, float]]:
    """Total the recorded LLM cost of a run, and break it down by model.

    Args:
        usage_summary: The ``llm_usage_summary.json`` data with a ``by_model``
            breakdown.

    Returns:
        Tuple of (total_cost_usd, {model_name: cost_usd}). Models whose calls
        carried no cost are omitted from the breakdown rather than listed at
        zero, and contribute nothing to the total.
    """
    by_model = usage_summary.get("by_model", {}) if isinstance(usage_summary, dict) else {}
    total_cost = 0.0
    cost_by_model: dict[str, float] = {}

    for model_name, bucket in by_model.items():
        _, priced_calls = bucket_call_counts(bucket)
        if not priced_calls:
            continue
        model_cost = coerce_float(bucket.get("cost_usd"))
        cost_by_model[model_name] = round(model_cost, 6)
        total_cost += model_cost

    return round(total_cost, 6), cost_by_model


def cost_status(usage_summary: dict | None) -> str:
    """Say how much of a run's LLM cost is known.

    Args:
        usage_summary: The ``llm_usage_summary.json`` data, or None.

    Returns:
        One of :data:`COMPLETE`, :data:`PARTIAL` or :data:`UNAVAILABLE`.
    """
    totals = usage_summary.get("totals", {}) if isinstance(usage_summary, dict) else {}
    calls, priced_calls = bucket_call_counts(totals)
    if not priced_calls:
        return UNAVAILABLE
    return COMPLETE if priced_calls >= calls else PARTIAL


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
