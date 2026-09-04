"""Tests for the dashboard's LLM cost readout."""

from metrics import costs


def _bucket(calls: int, calls_with_cost: int, **cost_fields: float) -> dict:
    """One post-change bucket as ``llm_usage_summary.json`` writes it."""
    bucket = {
        "calls": calls,
        "prompt_tokens": 1000 * calls,
        "completion_tokens": 500 * calls,
        "total_tokens": 1500 * calls,
        "reasoning_tokens": 0,
        "calls_with_cost": calls_with_cost,
        "cost_usd": 0.0,
        "prompt_cost_usd": 0.0,
        "completion_cost_usd": 0.0,
        "reasoning_cost_usd": 0.0,
    }
    bucket.update(cost_fields)
    return bucket


def _legacy_bucket(calls: int) -> dict:
    """One bucket as runs that predate cost recording wrote it: tokens only.

    Backwards compatibility is the point of this shape -- those runs carry no
    cost field at all, and their old figures came from a hand-maintained price
    table, so the dashboard must show a gap rather than a zero.
    """
    return {
        "calls": calls,
        "prompt_tokens": 1000 * calls,
        "completion_tokens": 500 * calls,
        "total_tokens": 1500 * calls,
        "reasoning_tokens": 0,
    }


def test_calculate_llm_cost_sums_recorded_cost_by_model() -> None:
    summary = {
        "totals": _bucket(5, 5, cost_usd=0.75),
        "by_model": {
            "openai/gpt-4o": _bucket(3, 3, cost_usd=0.5),
            "vertex_ai/gemini-2.5-pro": _bucket(2, 2, cost_usd=0.25),
        },
    }

    total, by_model = costs.calculate_llm_cost(summary)

    assert total == 0.75
    assert by_model == {"openai/gpt-4o": 0.5, "vertex_ai/gemini-2.5-pro": 0.25}


def test_calculate_llm_cost_omits_a_model_whose_calls_were_never_priced() -> None:
    """Copilot calls are unpriced, not free; listing them at $0 would be a lie."""
    summary = {
        "by_model": {
            "openai/gpt-4o": _bucket(3, 3, cost_usd=0.5),
            "github_copilot/gpt-4o": _bucket(40, 0),
        },
    }

    total, by_model = costs.calculate_llm_cost(summary)

    assert total == 0.5
    assert by_model == {"openai/gpt-4o": 0.5}
    assert "github_copilot/gpt-4o" not in by_model


def test_calculate_llm_cost_handles_a_summary_with_no_by_model() -> None:
    assert costs.calculate_llm_cost({}) == (0.0, {})
    assert costs.calculate_llm_cost({"by_model": {}}) == (0.0, {})


def test_calculate_llm_cost_rounds_to_the_cent_fraction_it_displays() -> None:
    summary = {"by_model": {"openai/gpt-4o": _bucket(1, 1, cost_usd=0.12345678)}}

    total, by_model = costs.calculate_llm_cost(summary)

    assert total == 0.123457
    assert by_model == {"openai/gpt-4o": 0.123457}


def test_cost_status_is_unavailable_for_a_run_that_predates_cost_recording() -> None:
    """The backwards-compatibility guarantee: no cost fields means no cost, not $0."""
    legacy_summary = {
        "totals": _legacy_bucket(5),
        "by_model": {"openai/gpt-4o": _legacy_bucket(5)},
        "by_agent": {"belief_agent": _legacy_bucket(5)},
        "by_node": {"node_2_0": _legacy_bucket(5)},
        "by_component": {"belief.main.prior": _legacy_bucket(5)},
    }

    assert costs.cost_status(legacy_summary) == costs.UNAVAILABLE
    assert costs.calculate_llm_cost(legacy_summary) == (0.0, {})


def test_cost_status_is_unavailable_when_no_call_was_priced() -> None:
    assert costs.cost_status({"totals": _bucket(40, 0)}) == costs.UNAVAILABLE
    assert costs.cost_status(None) == costs.UNAVAILABLE
    assert costs.cost_status({}) == costs.UNAVAILABLE


def test_cost_status_is_complete_when_every_call_was_priced() -> None:
    assert costs.cost_status({"totals": _bucket(5, 5, cost_usd=0.75)}) == costs.COMPLETE


def test_cost_status_is_partial_when_only_some_calls_were_priced() -> None:
    """A mixed-provider run knows part of its bill; the total is a lower bound."""
    assert costs.cost_status({"totals": _bucket(45, 5, cost_usd=0.75)}) == costs.PARTIAL


def test_bucket_call_counts_and_costs_tolerate_a_missing_bucket() -> None:
    assert costs.bucket_call_counts(None) == (0, 0)
    assert costs.bucket_call_counts(_legacy_bucket(5)) == (5, 0)
    assert costs.bucket_costs(None) == (0.0, 0.0, 0.0)
    assert costs.bucket_costs(_legacy_bucket(5)) == (0.0, 0.0, 0.0)
    assert costs.bucket_costs(
        _bucket(1, 1, cost_usd=0.75, prompt_cost_usd=0.25, completion_cost_usd=0.4)
    ) == (0.25, 0.4, 0.0)


def test_coercion_falls_back_to_zero_on_junk() -> None:
    assert costs.coerce_int("7") == 7
    assert costs.coerce_int(-3) == 0
    assert costs.coerce_int(None) == 0
    assert costs.coerce_int("nope") == 0
    assert costs.coerce_float("0.25") == 0.25
    assert costs.coerce_float(None) == 0.0
    assert costs.coerce_float("nope") == 0.0
