"""Tests for LLM usage tracking utilities."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from autodiscovery.llm_usage import (
    LOCAL_IMAGE_USAGE_MARKER,
    UsageTracker,
    extract_local_image_usage_markers,
)
from autodiscovery.utils import query_llm


class _FakeUsage:
    def __init__(
        self,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        completion_tokens_details: dict | None = None,
        prompt_tokens_details: dict | None = None,
    ):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.completion_tokens_details = completion_tokens_details
        self.prompt_tokens_details = prompt_tokens_details


class _FakeResponse:
    def __init__(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        cost: float | None = None,
    ):
        self.model = model
        self.usage = _FakeUsage(prompt_tokens, completion_tokens, total_tokens)
        if cost is not None:
            self.cost = cost


class _FakeMessage:
    def __init__(self, content: str):
        self.content = content
        self.parsed = None


class _FakeChoice:
    def __init__(self, content: str):
        self.message = _FakeMessage(content)


class _FakeChatResponse:
    def __init__(self, model: str, prompt_tokens: int, completion_tokens: int, total_tokens: int):
        self.model = model
        self.usage = _FakeUsage(prompt_tokens, completion_tokens, total_tokens)
        self.choices = [_FakeChoice('{"ok": true}')]


class _FakeTransport:
    """Stand-in for autodiscovery.llm.complete that records each call."""

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, spec, messages, **kwargs):
        self.calls.append({"model": str(spec), "messages": messages, **kwargs})
        n = int(kwargs.get("n", 1))
        return _FakeChatResponse(
            model=str(spec), prompt_tokens=10 * n, completion_tokens=2 * n, total_tokens=12 * n
        )


@pytest.fixture
def transport(monkeypatch):
    """Route autodiscovery.llm.complete at a recording fake."""
    fake = _FakeTransport()
    monkeypatch.setattr("autodiscovery.utils.llm.complete", fake)
    return fake


def test_usage_tracker_records_response_tokens() -> None:
    """Ensure direct response usage is captured as token usage."""
    tracker = UsageTracker()
    tracker.record_response(
        _FakeResponse("openai/gpt-4o", prompt_tokens=100, completion_tokens=20, total_tokens=120),
        source="openai",
        component="belief.main.posterior",
        agent_name="belief_agent",
        node_id="node_2_3",
    )

    summary = tracker.get_summary()
    assert summary["totals"]["calls"] == 1
    assert summary["totals"]["prompt_tokens"] == 100
    assert summary["totals"]["completion_tokens"] == 20
    assert summary["totals"]["total_tokens"] == 120
    assert summary["by_node"]["node_2_3"]["calls"] == 1
    assert summary["by_component"]["belief.main.posterior"]["calls"] == 1
    usage_payload = tracker._events[0]["usage"]
    assert usage_payload["prompt_tokens"] == 100
    assert usage_payload["completion_tokens"] == 20
    assert usage_payload["total_tokens"] == 120


def test_usage_tracker_preserves_optional_usage_details() -> None:
    """Ensure optional CompletionUsage detail fields are retained."""
    tracker = UsageTracker()
    tracker.record_response(
        {
            "model": "openai/gpt-4o",
            "usage": {
                "prompt_tokens": 42,
                "completion_tokens": 7,
                "total_tokens": 60,
                "completion_tokens_details": {"reasoning_tokens": 11},
                "prompt_tokens_details": {"cached_tokens": 5},
            },
        },
        source="openai",
        component="belief.main.posterior",
        agent_name="belief_agent",
        node_id="node_2_1",
    )

    usage_payload = tracker._events[0]["usage"]
    assert usage_payload["completion_tokens_details"]["reasoning_tokens"] == 11
    assert usage_payload["prompt_tokens_details"]["cached_tokens"] == 5
    summary = tracker.get_summary()
    assert summary["totals"]["reasoning_tokens"] == 11


def test_usage_tracker_records_agent_usage_deltas() -> None:
    """Ensure AG2 snapshot deltas are converted into usage events."""
    tracker = UsageTracker()
    before = {
        "experiment_generator": {
            "total_cost": 1.0,
            "gpt-4o": {
                "cost": 1.0,
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
    }
    after = {
        "experiment_generator": {
            "total_cost": 1.5,
            "gpt-4o": {
                "cost": 1.5,
                "prompt_tokens": 30,
                "completion_tokens": 15,
                "total_tokens": 45,
            },
        }
    }

    tracker.record_agent_usage_deltas(before, after, node_id="node_3_1")
    node_summary = tracker.get_node_summary("node_3_1")
    assert node_summary["totals"]["calls"] == 1
    assert node_summary["totals"]["prompt_tokens"] == 20
    assert node_summary["totals"]["completion_tokens"] == 10
    assert node_summary["totals"]["total_tokens"] == 30
    assert node_summary["totals"]["reasoning_tokens"] == 0


def test_extract_local_image_usage_markers() -> None:
    """Ensure local marker lines are parsed and removed from output text."""
    payload = {
        "source": "openai",
        "component": "image_analysis.local",
        "model": "openai/gpt-4o",
        "prompt_tokens": 42,
        "completion_tokens": 7,
        "total_tokens": 49,
    }
    text = "before\n" + LOCAL_IMAGE_USAGE_MARKER + json.dumps(payload) + "\n" + "after\n"

    entries, cleaned = extract_local_image_usage_markers(text)
    assert len(entries) == 1
    assert entries[0]["component"] == "image_analysis.local"
    assert cleaned == "before\nafter\n"


def test_usage_tracker_save_events_and_summary_separately(tmp_path: Path) -> None:
    """Ensure events can be persisted mid-run without writing summary."""
    tracker = UsageTracker()
    tracker.record_event(
        source="openai",
        component="belief.main.prior",
        model="openai/gpt-4o",
        prompt_tokens=10,
        completion_tokens=2,
        agent_name="belief_agent",
        node_id="node_2_0",
    )

    events_path = tmp_path / "llm_usage_events.jsonl"
    summary_path = tmp_path / "llm_usage_summary.json"

    tracker.save_events(str(tmp_path))
    assert events_path.exists()
    assert not summary_path.exists()

    tracker.save_summary(str(tmp_path))
    assert summary_path.exists()


def test_query_llm_records_usage_metadata(tmp_path: Path, transport) -> None:
    """Ensure query_llm records the per-request sample count as metadata."""
    tracker = UsageTracker()
    responses = query_llm(
        messages=[{"role": "user", "content": "Return JSON."}],
        n_samples=4,
        model="openai/gpt-4o",
        usage_tracker=tracker,
        usage_component="belief.main.prior",
        usage_agent_name="belief_agent",
        usage_node_id="node_2_0",
    )

    assert len(responses) == 1
    summary = tracker.get_summary()
    assert summary["totals"]["calls"] == 1
    assert summary["totals"]["total_tokens"] == 48

    events_path = tmp_path / "llm_usage_events.jsonl"
    tracker.save_events(str(tmp_path))
    with open(events_path) as f:
        event = json.loads(f.readline())
    assert event["metadata"]["n"] == 4
    assert "prompt_tokens" not in event
    assert "completion_tokens" not in event
    assert "total_tokens" not in event
    assert event["usage"]["prompt_tokens"] == 40
    assert event["usage"]["completion_tokens"] == 8
    assert event["usage"]["total_tokens"] == 48


def test_query_llm_records_actual_n_per_request(tmp_path: Path, transport) -> None:
    """Ensure metadata n reflects the actual n used for each batched request."""
    tracker = UsageTracker()
    _ = query_llm(
        messages=[{"role": "user", "content": "Return JSON."}],
        n_samples=30,
        model="openai/gpt-5-mini",
        usage_tracker=tracker,
        usage_component="belief.main.posterior",
        usage_agent_name="belief_agent",
        usage_node_id="node_2_0",
    )

    events_path = tmp_path / "llm_usage_events.jsonl"
    tracker.save_events(str(tmp_path))
    with open(events_path) as f:
        events = [json.loads(line) for line in f if line.strip()]

    assert [event["metadata"]["n"] for event in events] == [8, 8, 8, 6]


def test_query_llm_passes_reasoning_effort_for_gemini(transport) -> None:
    """Ensure Gemini requests include reasoning_effort."""
    _ = query_llm(
        messages=[{"role": "user", "content": "Return JSON."}],
        n_samples=1,
        model="vertex_ai/gemini-3-flash-preview",
        reasoning_effort="minimal",
    )

    assert len(transport.calls) == 1
    assert transport.calls[0]["model"] == "vertex_ai/gemini-3-flash-preview"
    assert transport.calls[0]["reasoning_effort"] == "minimal"


def test_query_llm_maps_minimal_reasoning_effort_for_openai_reasoning_models(transport) -> None:
    """Ensure o-series models, which lack minimal effort, map it to low."""
    _ = query_llm(
        messages=[{"role": "user", "content": "Return JSON."}],
        n_samples=1,
        model="openai/o4-mini",
        reasoning_effort="minimal",
    )

    assert transport.calls[0]["reasoning_effort"] == "low"


def test_query_llm_keeps_minimal_reasoning_effort_for_gpt5(transport) -> None:
    """The gpt-5 family accepts minimal effort; do not downgrade it.

    The old routing keyed off a ``gpt-5`` name prefix and downgraded the whole
    family. litellm records ``supports_minimal_reasoning_effort`` per model.
    """
    _ = query_llm(
        messages=[{"role": "user", "content": "Return JSON."}],
        n_samples=1,
        model="openai/gpt-5-mini",
        reasoning_effort="minimal",
    )

    assert transport.calls[0]["reasoning_effort"] == "minimal"


# --- cost recording --------------------------------------------------------


class _FakePricedResponse:
    """Stand-in for a litellm response, which carries its cost in _hidden_params."""

    def __init__(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        response_cost: float,
    ):
        self.model = model
        self.usage = _FakeUsage(prompt_tokens, completion_tokens, prompt_tokens + completion_tokens)
        self._hidden_params = {"response_cost": response_cost}


def _cost_fields(bucket: dict) -> dict:
    return {key: bucket[key] for key in bucket if key.endswith("_usd") or key == "calls_with_cost"}


def test_record_event_aggregates_cost_into_every_breakdown() -> None:
    """A recorded cost lands in totals and in each keyed breakdown alike."""
    tracker = UsageTracker()
    tracker.record_event(
        source="openai",
        component="belief.main.prior",
        model="openai/o4-mini",
        prompt_tokens=1000,
        completion_tokens=500,
        agent_name="belief_agent",
        node_id="node_2_0",
        cost={
            "total_usd": 0.0022,
            "prompt_usd": 0.0011,
            "completion_usd": 0.0004,
            "reasoning_usd": 0.0007,
        },
    )

    summary = tracker.get_summary()
    expected = {
        "calls_with_cost": 1,
        "cost_usd": 0.0022,
        "prompt_cost_usd": 0.0011,
        "completion_cost_usd": 0.0004,
        "reasoning_cost_usd": 0.0007,
    }
    assert _cost_fields(summary["totals"]) == expected
    assert _cost_fields(summary["by_model"]["openai/o4-mini"]) == expected
    assert _cost_fields(summary["by_agent"]["belief_agent"]) == expected
    assert _cost_fields(summary["by_node"]["node_2_0"]) == expected
    assert _cost_fields(summary["by_component"]["belief.main.prior"]) == expected


def test_record_event_sums_costs_across_calls() -> None:
    tracker = UsageTracker()
    for total, prompt in ((0.25, 0.10), (0.75, 0.30)):
        tracker.record_event(
            source="openai",
            component="belief.main.prior",
            model="openai/gpt-4o",
            prompt_tokens=10,
            completion_tokens=2,
            agent_name="belief_agent",
            cost={"total_usd": total, "prompt_usd": prompt, "completion_usd": total - prompt},
        )

    totals = tracker.get_summary()["totals"]
    assert totals["calls"] == 2
    assert totals["calls_with_cost"] == 2
    assert totals["cost_usd"] == 1.0
    assert totals["prompt_cost_usd"] == pytest.approx(0.4)
    assert totals["completion_cost_usd"] == pytest.approx(0.6)


def test_uncosted_calls_are_counted_but_priced_at_nothing() -> None:
    """calls_with_cost is what separates "these were free" from "nobody knows"."""
    tracker = UsageTracker()
    tracker.record_event(
        source="openai",
        component="belief.main.prior",
        model="github_copilot/gpt-4o",
        prompt_tokens=10,
        completion_tokens=2,
    )

    totals = tracker.get_summary()["totals"]
    assert totals["calls"] == 1
    assert totals["calls_with_cost"] == 0
    assert totals["cost_usd"] == 0.0
    assert totals["prompt_cost_usd"] == 0.0
    assert totals["completion_cost_usd"] == 0.0
    assert totals["reasoning_cost_usd"] == 0.0
    assert tracker._events[0]["cost"] is None


def test_a_bucket_may_mix_costed_and_uncosted_calls() -> None:
    """A partially-priced bucket reports its total as a lower bound, not a gap."""
    tracker = UsageTracker()
    tracker.record_event(
        source="openai",
        component="belief.main.prior",
        model="openai/gpt-4o",
        prompt_tokens=10,
        completion_tokens=2,
        cost={"total_usd": 0.25},
    )
    tracker.record_event(
        source="openai",
        component="belief.main.prior",
        model="openai/gpt-4o",
        prompt_tokens=10,
        completion_tokens=2,
    )

    bucket = tracker.get_summary()["by_component"]["belief.main.prior"]
    assert bucket["calls"] == 2
    assert bucket["calls_with_cost"] == 1
    assert bucket["cost_usd"] == 0.25


def test_record_response_prices_the_call_when_given_the_request_model() -> None:
    """A response reports a bare model name; pricing it needs the provider too."""
    tracker = UsageTracker()
    tracker.record_response(
        _FakePricedResponse(
            "gpt-4o", prompt_tokens=1000, completion_tokens=500, response_cost=0.0075
        ),
        source="openai",
        component="belief.main.prior",
        request_model="openai/gpt-4o",
    )

    cost = tracker._events[0]["cost"]
    assert cost["total_usd"] == 0.0075
    assert cost["prompt_usd"] + cost["completion_usd"] + cost["reasoning_usd"] == pytest.approx(
        0.0075, rel=1e-9
    )
    totals = tracker.get_summary()["totals"]
    assert totals["cost_usd"] == 0.0075
    assert totals["calls_with_cost"] == 1


def test_record_response_without_a_request_model_records_no_cost() -> None:
    tracker = UsageTracker()
    tracker.record_response(
        _FakePricedResponse(
            "gpt-4o", prompt_tokens=1000, completion_tokens=500, response_cost=0.0075
        ),
        source="openai",
        component="belief.main.prior",
    )

    assert tracker._events[0]["cost"] is None
    totals = tracker.get_summary()["totals"]
    assert totals["calls"] == 1
    assert totals["calls_with_cost"] == 0
    assert totals["cost_usd"] == 0.0


def _ag2_snapshot(cost: float | None, prompt: int, completion: int) -> dict:
    return {
        "experiment_generator": {
            "total_cost": cost,
            "gpt-4o": {
                "cost": cost,
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
            },
        }
    }


def test_agent_usage_deltas_carry_the_ag2_cost_delta_as_a_total() -> None:
    """AG2 only keeps a running total, so the delta has no prompt/completion split."""
    tracker = UsageTracker()
    tracker.record_agent_usage_deltas(
        _ag2_snapshot(1.0, 10, 5),
        _ag2_snapshot(1.5, 30, 15),
        node_id="node_3_1",
    )

    assert tracker._events[0]["cost"] == {"total_usd": 0.5}
    totals = tracker.get_node_summary("node_3_1")["totals"]
    assert totals["calls_with_cost"] == 1
    assert totals["cost_usd"] == 0.5
    assert totals["prompt_cost_usd"] == 0.0
    assert totals["completion_cost_usd"] == 0.0


def test_agent_usage_deltas_report_a_zero_cost_delta_as_unavailable() -> None:
    """AG2's interface forces an unpriced model to 0.0; real tokens cost something."""
    tracker = UsageTracker()
    tracker.record_agent_usage_deltas(
        _ag2_snapshot(0.0, 10, 5),
        _ag2_snapshot(0.0, 30, 15),
        node_id="node_3_1",
    )

    assert tracker._events[0]["cost"] is None
    totals = tracker.get_node_summary("node_3_1")["totals"]
    assert totals["calls"] == 1
    assert totals["prompt_tokens"] == 20
    assert totals["calls_with_cost"] == 0
    assert totals["cost_usd"] == 0.0
