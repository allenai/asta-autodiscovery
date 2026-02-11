"""Tests for LLM usage tracking utilities."""

from __future__ import annotations

import json
from pathlib import Path

from autodiscovery.llm_usage import (
    LOCAL_IMAGE_USAGE_MARKER,
    PricingEntry,
    UsageTracker,
    build_priced_summary,
    extract_local_image_usage_markers,
    price_usage_events,
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


class _FakeCompletions:
    def create(self, **kwargs):
        n = int(kwargs.get("n", 1))
        return _FakeChatResponse(
            model=str(kwargs.get("model", "gpt-4o")),
            prompt_tokens=10 * n,
            completion_tokens=2 * n,
            total_tokens=12 * n,
        )


class _FakeChat:
    def __init__(self):
        self.completions = _FakeCompletions()


class _FakeClient:
    def __init__(self):
        self.chat = _FakeChat()


def test_usage_tracker_records_response_tokens() -> None:
    """Ensure direct response usage is captured as token usage."""
    tracker = UsageTracker()
    tracker.record_response(
        _FakeResponse("gpt-4o", prompt_tokens=100, completion_tokens=20, total_tokens=120),
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
            "model": "gpt-4o",
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


def test_price_usage_events_and_summary() -> None:
    """Ensure post-processing pricing annotates events and summary correctly."""
    events = [
        {
            "source": "ag2",
            "component": "agents.chat",
            "agent_name": "experiment_generator",
            "node_id": "node_2_0",
            "model": "gemini-3-flash-preview",
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 100,
                "total_tokens": 1100,
                "completion_tokens_details": {"reasoning_tokens": 45},
            },
            "metadata": {},
        }
    ]
    pricing = {
        "gemini-3-flash-preview": PricingEntry(prompt_per_1k=0.0005, completion_per_1k=0.003)
    }

    priced_events = price_usage_events(events, pricing)
    assert priced_events[0]["unpriced"] is False
    assert priced_events[0]["cost_usd"] == 0.0008

    summary = build_priced_summary(priced_events)
    assert summary["totals"]["calls"] == 1
    assert summary["totals"]["total_tokens"] == 1100
    assert summary["totals"]["reasoning_tokens"] == 45
    assert summary["totals"]["cost_usd"] == 0.0008
    assert summary["unpriced_models"] == []


def test_extract_local_image_usage_markers() -> None:
    """Ensure local marker lines are parsed and removed from output text."""
    payload = {
        "source": "openai",
        "component": "image_analysis.local",
        "model": "gpt-4o",
        "prompt_tokens": 42,
        "completion_tokens": 7,
        "total_tokens": 49,
    }
    text = (
        "before\n"
        + LOCAL_IMAGE_USAGE_MARKER
        + json.dumps(payload)
        + "\n"
        + "after\n"
    )

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
        model="gpt-4o",
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


def test_query_llm_records_usage_metadata(tmp_path: Path) -> None:
    """Ensure query_llm records the per-request sample count as metadata."""
    tracker = UsageTracker()
    responses = query_llm(
        messages=[{"role": "user", "content": "Return JSON."}],
        n_samples=4,
        model="gpt-4o",
        client=_FakeClient(),
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


def test_query_llm_records_actual_n_per_request(tmp_path: Path) -> None:
    """Ensure metadata n reflects the actual n used for each batched request."""
    tracker = UsageTracker()
    _ = query_llm(
        messages=[{"role": "user", "content": "Return JSON."}],
        n_samples=30,
        model="gpt-5-mini",
        client=_FakeClient(),
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
