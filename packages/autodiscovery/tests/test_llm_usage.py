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


class _CostedResponse:
    """A litellm-shaped response carrying the cost litellm computed."""

    def __init__(self, model: str, cost: float | None, **tokens: int):
        self.model = model
        self.usage = _FakeUsage(**tokens)
        self._hidden_params = {} if cost is None else {"response_cost": cost}


def test_usage_tracker_records_litellm_cost() -> None:
    """litellm's own per-call cost is recorded and aggregated, not re-derived."""
    tracker = UsageTracker()
    tracker.record_response(
        _CostedResponse(
            "openai/gpt-4o",
            0.5,
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
        ),
        source="openai",
        component="belief.main.posterior",
        agent_name="belief_agent",
        node_id="node_2_3",
    )

    summary = tracker.get_summary()
    totals = summary["totals"]
    assert totals["calls_with_cost"] == 1
    assert totals["cost_usd"] == pytest.approx(0.5)
    # The prompt/output attribution always sums back to litellm's total.
    assert totals["prompt_cost_usd"] + totals["completion_cost_usd"] + totals[
        "reasoning_cost_usd"
    ] == pytest.approx(0.5)
    assert summary["by_model"]["openai/gpt-4o"]["cost_usd"] == pytest.approx(0.5)
    assert summary["by_agent"]["belief_agent"]["cost_usd"] == pytest.approx(0.5)
    assert summary["by_node"]["node_2_3"]["cost_usd"] == pytest.approx(0.5)


def test_usage_tracker_leaves_unpriced_calls_uncosted() -> None:
    """A call litellm cannot price is unknown, not free -- and is flagged as such."""
    tracker = UsageTracker()
    tracker.record_response(
        _CostedResponse(
            "github_copilot/gpt-4o",
            None,
            prompt_tokens=100,
            completion_tokens=20,
            total_tokens=120,
        ),
        source="github_copilot",
        component="agents.chat",
    )

    summary = tracker.get_summary()
    assert summary["totals"]["calls"] == 1
    assert summary["totals"]["calls_with_cost"] == 0
    assert summary["totals"]["cost_usd"] == 0.0
    assert tracker._events[0]["cost"] is None


def test_usage_tracker_splits_output_cost_across_reasoning() -> None:
    """The output share of a call's cost is attributed by completion/reasoning tokens."""
    tracker = UsageTracker()
    tracker.record_response(
        {
            "model": "openai/o4-mini",
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 30,
                "total_tokens": 120,
                "completion_tokens_details": {"reasoning_tokens": 90},
            },
            "_hidden_params": {"response_cost": 1.0},
        },
        source="openai",
        component="agents.chat",
    )

    totals = tracker.get_summary()["totals"]
    assert totals["cost_usd"] == pytest.approx(1.0)
    assert totals["prompt_cost_usd"] == pytest.approx(0.0)
    assert totals["completion_cost_usd"] == pytest.approx(0.25)
    assert totals["reasoning_cost_usd"] == pytest.approx(0.75)


def test_usage_tracker_records_agent_usage_delta_cost() -> None:
    """AG2 summary-delta mode carries litellm's cost through too."""
    tracker = UsageTracker()
    before = {"belief_agent": {"openai/gpt-4o": {"prompt_tokens": 10, "completion_tokens": 2,
                                                 "total_tokens": 12, "cost": 0.1}}}
    after = {"belief_agent": {"openai/gpt-4o": {"prompt_tokens": 30, "completion_tokens": 6,
                                                "total_tokens": 36, "cost": 0.4}}}
    tracker.record_agent_usage_deltas(before, after, node_id="node_3_1")

    totals = tracker.get_summary()["totals"]
    assert totals["calls_with_cost"] == 1
    assert totals["cost_usd"] == pytest.approx(0.3)
