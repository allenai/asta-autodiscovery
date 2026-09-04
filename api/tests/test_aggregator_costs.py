"""Tests for per-event cost breakdowns built by the metrics aggregator."""

import pytest
from metrics import aggregator


def _event(
    *,
    agent_name: str | None,
    component: str,
    node_id: str | None,
    cost: dict | None,
) -> dict:
    return {
        "source": "openai",
        "component": component,
        "agent_name": agent_name,
        "node_id": node_id,
        "model": "openai/gpt-4o",
        "cost": cost,
        "usage": {"prompt_tokens": 1000, "completion_tokens": 500, "total_tokens": 1500},
    }


def test_event_cost_breakdowns_sum_recorded_costs_by_agent_component_and_node() -> None:
    events = [
        _event(
            agent_name="belief_agent",
            component="belief.main.prior",
            node_id="node_2_0",
            cost={
                "total_usd": 0.75,
                "prompt_usd": 0.25,
                "completion_usd": 0.3,
                "reasoning_usd": 0.2,
            },
        ),
        _event(
            agent_name="belief_agent",
            component="belief.main.posterior",
            node_id="node_2_0",
            cost={
                "total_usd": 0.25,
                "prompt_usd": 0.1,
                "completion_usd": 0.15,
                "reasoning_usd": 0.0,
            },
        ),
    ]

    by_agent, by_component, by_node = aggregator._build_event_cost_breakdowns(events)

    assert by_agent["belief_agent"] == pytest.approx(
        {
            "total_cost_usd": 1.0,
            "prompt_cost_usd": 0.35,
            "completion_cost_usd": 0.45,
            "reasoning_cost_usd": 0.2,
            "calls": 2,
            "priced_calls": 2,
        }
    )
    # Both events share an agent and a node, so only the component splits them.
    assert by_node["node_2_0"] == by_agent["belief_agent"]
    assert by_component["belief.main.prior"]["total_cost_usd"] == 0.75
    assert by_component["belief.main.posterior"]["total_cost_usd"] == 0.25
    assert by_component["belief.main.prior"]["calls"] == 1


def test_event_cost_breakdowns_count_unpriced_calls_separately() -> None:
    """priced_calls below calls is what marks a bucket's total as a lower bound."""
    events = [
        _event(
            agent_name="belief_agent",
            component="belief.main.prior",
            node_id="node_2_0",
            cost={"total_usd": 0.75, "prompt_usd": 0.25, "completion_usd": 0.5},
        ),
        _event(
            agent_name="belief_agent",
            component="belief.main.prior",
            node_id="node_2_0",
            cost=None,
        ),
    ]

    by_agent, _, _ = aggregator._build_event_cost_breakdowns(events)

    assert by_agent["belief_agent"]["calls"] == 2
    assert by_agent["belief_agent"]["priced_calls"] == 1
    assert by_agent["belief_agent"]["total_cost_usd"] == 0.75
    assert by_agent["belief_agent"]["reasoning_cost_usd"] == 0.0


def test_event_cost_breakdowns_fall_back_to_placeholder_keys() -> None:
    events = [_event(agent_name=None, component="", node_id=None, cost=None)]

    by_agent, by_component, by_node = aggregator._build_event_cost_breakdowns(events)

    assert set(by_agent) == {"unassigned"}
    assert set(by_component) == {"unknown"}
    assert set(by_node) == {"run_level"}
    assert by_agent["unassigned"]["calls"] == 1
    assert by_agent["unassigned"]["priced_calls"] == 0


def test_event_cost_reads_only_a_cost_with_a_total() -> None:
    """A legacy event has no cost key at all; a malformed one has no total."""
    assert aggregator._event_cost({"cost": None}) is None
    assert aggregator._event_cost({}) is None
    assert aggregator._event_cost({"cost": {"prompt_usd": 0.25}}) is None
    assert aggregator._event_cost({"cost": {"total_usd": 0.25}}) == {
        "total_cost_usd": 0.25,
        "prompt_cost_usd": 0.0,
        "completion_cost_usd": 0.0,
        "reasoning_cost_usd": 0.0,
    }
