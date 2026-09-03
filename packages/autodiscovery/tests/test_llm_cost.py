"""Tests for per-call cost reporting from litellm."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from autodiscovery.llm import cost_of, reported_cost

# Prices come from litellm's registry and drift with it, so nothing here asserts
# a per-token rate. The invariants are what the callers rely on: the total is
# whatever litellm reported for the call, and the split adds back up to it.
#
# The split is scaled onto the reported total, so "adds back up" is exact only
# to float precision; EXACT pins that at a relative 1e-12 rather than letting a
# real drift hide behind a loose tolerance.
EXACT = 1e-12


def _response(
    *,
    response_cost: float | None,
    prompt_tokens: int,
    completion_tokens: int,
    reasoning_tokens: int | None = None,
) -> SimpleNamespace:
    completion_details = (
        {"reasoning_tokens": reasoning_tokens} if reasoning_tokens is not None else None
    )
    return SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            completion_tokens_details=completion_details,
        ),
        model="gpt-4o",
        _hidden_params={} if response_cost is None else {"response_cost": response_cost},
    )


def _parts_sum(cost: dict[str, float]) -> float:
    return cost["prompt_usd"] + cost["completion_usd"] + cost["reasoning_usd"]


def test_priced_model_reports_litellms_total_and_a_split_that_sums_to_it() -> None:
    response = _response(response_cost=0.0075, prompt_tokens=1000, completion_tokens=500)

    cost = cost_of(response, "openai/gpt-4o")

    assert cost is not None
    # The total is litellm's own figure, never recomputed from token prices.
    assert cost["total_usd"] == 0.0075
    assert _parts_sum(cost) == pytest.approx(0.0075, rel=EXACT)
    assert cost["prompt_usd"] > 0
    assert cost["completion_usd"] > 0
    assert cost["reasoning_usd"] == 0.0


def test_copilot_reports_unknown_rather_than_zero() -> None:
    """Copilot bills premium requests, so litellm's zero token price is not a price.

    This is the regression the whole cost-recording change exists to prevent:
    reporting a real run as free because the provider is not billed per token.
    """
    response = _response(response_cost=0.0, prompt_tokens=1000, completion_tokens=500)

    assert cost_of(response, "github_copilot/gpt-4o") is None
    assert cost_of(response, "github_copilot/claude-haiku-4.5") is None


def test_model_litellm_has_not_mapped_reports_unknown() -> None:
    """Preview models ship before litellm prices them; that is unknown, not free."""
    response = _response(response_cost=0.01, prompt_tokens=1000, completion_tokens=500)

    assert cost_of(response, "vertex_ai/gemini-4.7-pro-preview") is None


def test_reasoning_cost_is_carved_out_of_the_completion_cost() -> None:
    """Reasoning tokens are a subset of completion tokens, not an addition to them."""
    response = _response(
        response_cost=0.0022,
        prompt_tokens=1000,
        completion_tokens=500,
        reasoning_tokens=400,
    )

    cost = cost_of(response, "openai/o4-mini")

    assert cost is not None
    assert cost["total_usd"] == 0.0022
    assert _parts_sum(cost) == pytest.approx(0.0022, rel=EXACT)
    # 400 of the 500 completion tokens were reasoning, so reasoning takes 4/5 of
    # the completion cost and the remaining completion_usd keeps the other 1/5.
    output_usd = cost["completion_usd"] + cost["reasoning_usd"]
    assert cost["reasoning_usd"] == pytest.approx(output_usd * 0.8, rel=EXACT)
    assert cost["completion_usd"] == pytest.approx(output_usd * 0.2, rel=EXACT)


def test_reasoning_tokens_are_clamped_to_the_completion_count() -> None:
    """A reasoning count above completion_tokens must not exceed the output cost."""
    response = _response(
        response_cost=0.0022,
        prompt_tokens=1000,
        completion_tokens=500,
        reasoning_tokens=900,
    )

    cost = cost_of(response, "openai/o4-mini")

    assert cost is not None
    assert _parts_sum(cost) == pytest.approx(0.0022, rel=EXACT)
    assert cost["completion_usd"] == 0.0


def test_a_discounted_total_keeps_litellms_figure_and_rescales_the_split() -> None:
    """A cache read makes response_cost lower than a plain prompt/completion split.

    ``response_cost`` also covers cache reads, image input and built-in tools, so
    the two disagree on some calls; the reported total wins and the split is
    scaled onto it.
    """
    tokens = {"prompt_tokens": 1000, "completion_tokens": 500}
    undiscounted = cost_of(_response(response_cost=0.0075, **tokens), "openai/gpt-4o")
    discounted = cost_of(_response(response_cost=0.002, **tokens), "openai/gpt-4o")

    assert undiscounted is not None
    assert discounted is not None
    assert discounted["total_usd"] == 0.002
    assert _parts_sum(discounted) == pytest.approx(0.002, rel=EXACT)
    # Same tokens, so the split keeps its shape and only its scale changes.
    assert discounted["total_usd"] < undiscounted["total_usd"]
    assert discounted["prompt_usd"] / discounted["completion_usd"] == pytest.approx(
        undiscounted["prompt_usd"] / undiscounted["completion_usd"], rel=EXACT
    )


def test_a_zero_token_call_is_free_rather_than_unpriced() -> None:
    """Zero cost over zero tokens is a real answer; zero over real tokens is not."""
    response = _response(response_cost=0.0, prompt_tokens=0, completion_tokens=0)

    assert cost_of(response, "openai/gpt-4o") == {"total_usd": 0.0}


def test_reported_cost_is_none_without_hidden_params() -> None:
    assert reported_cost(SimpleNamespace(model="gpt-4o")) is None
    assert reported_cost(SimpleNamespace(model="gpt-4o", _hidden_params={})) is None
    assert reported_cost(SimpleNamespace(_hidden_params={"response_cost": None})) is None
    assert reported_cost(SimpleNamespace(_hidden_params={"response_cost": 0.25})) == 0.25


def test_cost_of_falls_back_to_the_token_split_when_nothing_was_reported() -> None:
    """A response with no ``response_cost`` is still priceable from its tokens."""
    reported = cost_of(
        _response(response_cost=0.0075, prompt_tokens=1000, completion_tokens=500),
        "openai/gpt-4o",
    )
    unreported = cost_of(
        _response(response_cost=None, prompt_tokens=1000, completion_tokens=500),
        "openai/gpt-4o",
    )

    assert reported is not None
    assert unreported is not None
    assert _parts_sum(unreported) == pytest.approx(unreported["total_usd"], rel=EXACT)
    # 0.0075 is exactly litellm's own gpt-4o split for these tokens today, so the
    # fallback and the reported figure agree; assert the relationship, not a rate.
    assert unreported["prompt_usd"] / unreported["completion_usd"] == pytest.approx(
        reported["prompt_usd"] / reported["completion_usd"], rel=EXACT
    )
