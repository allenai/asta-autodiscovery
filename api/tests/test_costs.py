from datetime import UTC, datetime

import pytest
from metrics import costs
from metrics.costs import _FALLBACK_PRICING, _lookup_pricing, calculate_llm_cost


@pytest.mark.parametrize(
    "model", ["vertex_ai/gemini-3.8-flash", "vertex_ai/gemini-3.5-flash", "gemini-3.8-flash"]
)
def test_gemini_migration_targets_are_priced(model: str) -> None:
    """Models replacing gemini-3.7-flash must not be costed at the fallback rate."""
    assert _lookup_pricing(model) != _FALLBACK_PRICING


@pytest.mark.parametrize(
    "model",
    [
        "gemini-3.8-flash",
        "vertex_ai/gemini-3.8-flash",
        "gemini-3.7-flash",
        "vertex_ai/gemini-3.7-flash",
    ],
)
@pytest.mark.parametrize(
    ("usage_at", "expected"),
    [
        ("2026-12-31T23:59:59.999999Z", {"input": 0.75, "output": 3.75}),
        ("2027-01-01T00:00:00Z", {"input": 1.50, "output": 7.50}),
        ("2027-01-28T12:00:00Z", {"input": 1.50, "output": 7.50}),
        ("2027-01-01T00:30:00+01:00", {"input": 0.75, "output": 3.75}),
        ("2026-12-31T23:30:00-01:00", {"input": 1.50, "output": 7.50}),
        ("2027-01-01T00:00:00", {"input": 1.50, "output": 7.50}),
    ],
)
def test_gemini_flash_promotional_pricing(model, usage_at, expected) -> None:
    assert _lookup_pricing(model, usage_at=usage_at) == expected


@pytest.mark.parametrize("usage_at", [None, "", "invalid"])
@pytest.mark.parametrize(
    ("now", "expected"),
    [(datetime(2026, 12, 31, tzinfo=UTC), 0.75), (datetime(2027, 1, 1, tzinfo=UTC), 1.50)],
)
def test_missing_usage_time_uses_current_rate(monkeypatch, usage_at, now, expected):
    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now

    monkeypatch.setattr(costs, "datetime", FrozenDateTime)
    assert _lookup_pricing("gemini-3.8-flash", usage_at=usage_at)["input"] == expected


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("vertex_ai/gemini-3.5-flash", {"input": 1.50, "output": 9.00}),
        ("unknown/model", _FALLBACK_PRICING),
    ],
)
def test_other_model_rates_are_unchanged(model, expected):
    for usage_at in ("2026-12-31", "2027-01-28"):
        assert _lookup_pricing(model, usage_at=usage_at) == expected


@pytest.mark.parametrize(("usage_at", "expected"), [("2026-12-31", 4.5), ("2027-01-01", 9.0)])
def test_total_cost_uses_historical_rate(usage_at, expected):
    model = "vertex_ai/gemini-3.8-flash"
    usage = {"by_model": {model: {"prompt_tokens": 1_000_000, "total_tokens": 2_000_000}}}
    assert calculate_llm_cost(usage, usage_at=usage_at) == (expected, {model: expected})
