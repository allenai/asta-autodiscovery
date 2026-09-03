"""Utilities for tracking LLM token usage."""

from __future__ import annotations

import copy
import json
import os
import threading
from dataclasses import asdict, is_dataclass
from datetime import UTC, datetime
from typing import Any

LOCAL_IMAGE_USAGE_MARKER = "__AUTODISCOVERY_LLM_USAGE__"
_AG2_USAGE_TRACKER = None
_AG2_USAGE_CONTEXT = threading.local()


def load_usage_events(events_path: str) -> list[dict[str, Any]]:
    """Load usage events from JSONL.

    Args:
        events_path: Path to ``llm_usage_events.jsonl``.

    Returns:
        List of parsed event dictionaries.
    """
    events: list[dict[str, Any]] = []
    with open(events_path) as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                events.append(parsed)
    return events


def save_usage_events(events: list[dict[str, Any]], out_path: str) -> None:
    """Save usage events to JSONL.

    Args:
        events: Event dictionaries.
        out_path: Output path.
    """
    with open(out_path, "w") as f:
        for event in events:
            f.write(json.dumps(event))
            f.write("\n")


def snapshot_agents_actual_usage(agents: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Snapshot AG2 actual usage summaries for a set of agents.

    Args:
        agents: Mapping of agent name to agent object.

    Returns:
        Mapping of agent name to usage summary dictionary.
    """
    snapshots: dict[str, dict[str, Any]] = {}
    for agent_name, agent in agents.items():
        getter = getattr(agent, "get_actual_usage", None)
        if not callable(getter):
            continue
        usage = getter() or {}
        if isinstance(usage, dict):
            snapshots[agent_name] = copy.deepcopy(usage)
    return snapshots


def extract_local_image_usage_markers(text: str) -> tuple[list[dict[str, Any]], str]:
    """Extract JSON usage markers emitted by local image-analysis patches.

    Args:
        text: Raw text output.

    Returns:
        Tuple of parsed usage entries and cleaned text with marker lines removed.
    """
    if not text:
        return [], text

    usage_entries: list[dict[str, Any]] = []
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        marker_idx = line.find(LOCAL_IMAGE_USAGE_MARKER)
        if marker_idx < 0:
            cleaned_lines.append(line)
            continue

        payload = line[marker_idx + len(LOCAL_IMAGE_USAGE_MARKER) :].strip()
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            cleaned_lines.append(line)
            continue
        if isinstance(parsed, dict):
            usage_entries.append(parsed)

    cleaned_text = "\n".join(cleaned_lines)
    if text.endswith("\n"):
        cleaned_text += "\n"
    return usage_entries, cleaned_text


class UsageTracker:
    """Collects per-call token usage events and aggregate summaries."""

    def __init__(self):
        """Initialize a usage tracker."""
        self._lock = threading.Lock()
        self._events: list[dict[str, Any]] = []

    def record_event(
        self,
        *,
        source: str,
        component: str,
        model: str | None,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int | None = None,
        agent_name: str | None = None,
        node_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        usage: Any | None = None,
        cost: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Record one token-usage event.

        Args:
            source: Source identifier (for example, ``ag2`` or ``openai``).
            component: Component label for the call path.
            model: Model name.
            prompt_tokens: Prompt/input token count.
            completion_tokens: Completion/output token count.
            total_tokens: Optional total token count.
            agent_name: Optional agent name.
            node_id: Optional node identifier.
            metadata: Optional metadata map.
            usage: Optional raw provider usage payload in standardized response form.
            cost: Optional cost breakdown, as returned by
                :func:`autodiscovery.llm.cost_of`. ``None`` records the call's cost
                as unavailable, which is not the same as a cost of zero.

        Returns:
            The recorded event dictionary.
        """
        prompt = max(0, int(prompt_tokens))
        completion = max(0, int(completion_tokens))
        total = max(0, int(total_tokens if total_tokens is not None else prompt + completion))

        event = {
            "ts": datetime.now(UTC).isoformat(),
            "source": source,
            "component": component,
            "agent_name": agent_name,
            "node_id": node_id,
            "model": model,
            "metadata": metadata or {},
            "cost": _normalize_cost(cost),
        }
        usage_payload = _usage_payload_with_token_counts(
            usage=usage,
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
        )
        event["usage"] = usage_payload
        with self._lock:
            self._events.append(event)
        return event

    def record_response(
        self,
        response: Any,
        *,
        source: str,
        component: str,
        request_model: str | None = None,
        agent_name: str | None = None,
        node_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """Record usage from an OpenAI-compatible response object.

        Args:
            response: API response object that may contain ``usage`` and ``model``.
            source: Source identifier.
            component: Component label for the call path.
            request_model: The litellm-qualified model name the request was made
                with. Supplying it records what the call cost; without it the
                event's cost is unavailable, because pricing a call needs the
                provider and a response only reports the bare model name.
            agent_name: Optional agent name.
            node_id: Optional node identifier.
            metadata: Optional metadata map.

        Returns:
            The recorded event dictionary, or ``None`` when usage data is unavailable.
        """
        usage = _extract_usage_from_response(response)
        if usage is None:
            return None
        return self.record_event(
            source=source,
            component=component,
            model=usage.get("model"),
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            agent_name=agent_name,
            node_id=node_id,
            metadata=dict(metadata or {}),
            usage=usage.get("usage"),
            cost=_response_cost(response, request_model),
        )

    def record_agent_usage_deltas(
        self,
        before_usage: dict[str, dict[str, Any]],
        after_usage: dict[str, dict[str, Any]],
        *,
        node_id: str | None,
        component: str = "agents",
    ) -> None:
        """Record AG2 per-agent usage deltas between two snapshots.

        Args:
            before_usage: Agent usage snapshot taken before work.
            after_usage: Agent usage snapshot taken after work.
            node_id: Optional node identifier to assign to recorded events.
            component: Component label for emitted events.
        """
        for agent_name, after_summary in after_usage.items():
            before_summary = before_usage.get(agent_name, {})
            for model_name, model_usage in after_summary.items():
                if model_name == "total_cost" or not isinstance(model_usage, dict):
                    continue
                prev_usage = before_summary.get(model_name, {})
                prompt = _positive_delta(
                    model_usage.get("prompt_tokens"),
                    prev_usage.get("prompt_tokens"),
                )
                completion = _positive_delta(
                    model_usage.get("completion_tokens"),
                    prev_usage.get("completion_tokens"),
                )
                total = _positive_delta(
                    model_usage.get("total_tokens"),
                    prev_usage.get("total_tokens"),
                )
                if prompt == 0 and completion == 0 and total == 0:
                    continue
                self.record_event(
                    source="ag2",
                    component=component,
                    model=model_name,
                    prompt_tokens=prompt,
                    completion_tokens=completion,
                    total_tokens=total,
                    agent_name=agent_name,
                    node_id=node_id,
                    cost=_delta_cost(model_usage, prev_usage),
                )

    def get_node_summary(self, node_id: str) -> dict[str, Any]:
        """Return aggregate usage summary for a single node.

        Args:
            node_id: Node identifier.

        Returns:
            Aggregate summary dictionary scoped to the node.
        """
        with self._lock:
            node_events = [event for event in self._events if event.get("node_id") == node_id]
        return _build_summary(node_events)

    def get_summary(self) -> dict[str, Any]:
        """Return aggregate usage summary across all events.

        Returns:
            Aggregate summary dictionary.
        """
        with self._lock:
            events = copy.deepcopy(self._events)
        return _build_summary(events)

    def save_events(self, log_dirname: str) -> None:
        """Persist raw usage events to disk.

        Args:
            log_dirname: Output log directory.
        """
        os.makedirs(log_dirname, exist_ok=True)
        with self._lock:
            events = copy.deepcopy(self._events)

        events_path = os.path.join(log_dirname, "llm_usage_events.jsonl")
        save_usage_events(events, events_path)

    def save_summary(self, log_dirname: str) -> None:
        """Persist aggregate usage summary to disk.

        Args:
            log_dirname: Output log directory.
        """
        os.makedirs(log_dirname, exist_ok=True)
        with self._lock:
            events = copy.deepcopy(self._events)

        summary = _build_summary(events)
        summary_path = os.path.join(log_dirname, "llm_usage_summary.json")

        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

    def save(self, log_dirname: str) -> None:
        """Persist both raw usage events and aggregate summary to disk.

        Args:
            log_dirname: Output log directory.
        """
        self.save_events(log_dirname)
        self.save_summary(log_dirname)


def configure_ag2_usage_tracking(tracker: UsageTracker | None) -> None:
    """Configure global tracker used by AG2 per-response usage hooks.

    Args:
        tracker: Usage tracker instance, or ``None`` to disable AG2 hook recording.
    """
    global _AG2_USAGE_TRACKER
    _AG2_USAGE_TRACKER = tracker


def set_ag2_usage_context(
    *,
    node_id: str | None,
    component: str = "agents.chat",
) -> None:
    """Set thread-local context for AG2 per-response usage events.

    Args:
        node_id: Node id to attach to AG2 response usage events.
        component: Component label for AG2 response usage events.
    """
    _AG2_USAGE_CONTEXT.node_id = node_id
    _AG2_USAGE_CONTEXT.component = component


def clear_ag2_usage_context() -> None:
    """Clear thread-local context for AG2 per-response usage events."""
    if hasattr(_AG2_USAGE_CONTEXT, "node_id"):
        del _AG2_USAGE_CONTEXT.node_id
    if hasattr(_AG2_USAGE_CONTEXT, "component"):
        del _AG2_USAGE_CONTEXT.component


def record_ag2_response_usage(
    response: Any,
    *,
    agent_name: str | None = None,
    request_model: str | None = None,
) -> dict[str, Any] | None:
    """Record one AG2 response usage event using configured global context.

    Args:
        response: OpenAI-compatible response returned by AG2.
        agent_name: Optional agent name for attribution.
        request_model: The litellm-qualified model name the request was made with.

    Returns:
        The recorded event dictionary, or ``None`` if tracking is disabled or
        usage payload is unavailable.
    """
    tracker = _AG2_USAGE_TRACKER
    if tracker is None:
        return None
    node_id = getattr(_AG2_USAGE_CONTEXT, "node_id", None)
    component = getattr(_AG2_USAGE_CONTEXT, "component", "agents.chat")
    return tracker.record_response(
        response,
        source="ag2",
        component=component,
        request_model=request_model,
        agent_name=agent_name,
        node_id=node_id,
    )


def _build_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Build aggregate summaries from raw usage events."""
    summary = {
        "totals": _empty_bucket(),
        "by_model": {},
        "by_agent": {},
        "by_node": {},
        "by_component": {},
    }
    for event in events:
        _accumulate(summary["totals"], event)
        _accumulate(summary["by_model"], event, key=event.get("model") or "unknown")
        _accumulate(summary["by_agent"], event, key=event.get("agent_name") or "unassigned")
        _accumulate(summary["by_node"], event, key=event.get("node_id") or "run_level")
        _accumulate(summary["by_component"], event, key=event.get("component") or "unknown")
    return summary


def _accumulate(target: dict[str, Any], event: dict[str, Any], key: str | None = None) -> None:
    """Accumulate one event into an aggregate bucket."""
    bucket = target if key is None else target.setdefault(key, _empty_bucket())
    prompt, completion, total = _event_token_counts(event)
    reasoning = _event_reasoning_tokens(event)
    bucket["calls"] += 1
    bucket["prompt_tokens"] += prompt
    bucket["completion_tokens"] += completion
    bucket["total_tokens"] += total
    bucket["reasoning_tokens"] += reasoning

    cost = event.get("cost")
    if not isinstance(cost, dict):
        return
    # Counted separately from ``calls`` so a consumer can tell "these calls cost
    # nothing" from "nobody knows what these calls cost" -- the two are only
    # distinguishable at this granularity, and a bucket may hold both.
    bucket["calls_with_cost"] += 1
    bucket["cost_usd"] += float(cost.get("total_usd") or 0.0)
    bucket["prompt_cost_usd"] += float(cost.get("prompt_usd") or 0.0)
    bucket["completion_cost_usd"] += float(cost.get("completion_usd") or 0.0)
    bucket["reasoning_cost_usd"] += float(cost.get("reasoning_usd") or 0.0)


def _empty_bucket() -> dict[str, Any]:
    """Return an empty aggregate bucket."""
    return {
        "calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "calls_with_cost": 0,
        "cost_usd": 0.0,
        "prompt_cost_usd": 0.0,
        "completion_cost_usd": 0.0,
        "reasoning_cost_usd": 0.0,
    }


def _normalize_cost(cost: dict[str, float] | None) -> dict[str, float] | None:
    """Coerce a cost breakdown into JSON-safe floats, or None if unusable."""
    if not isinstance(cost, dict):
        return None
    normalized: dict[str, float] = {}
    for key in ("total_usd", "prompt_usd", "completion_usd", "reasoning_usd"):
        if cost.get(key) is None:
            continue
        try:
            normalized[key] = round(float(cost[key]), 12)
        except (TypeError, ValueError):
            continue
    return normalized if "total_usd" in normalized else None


def _response_cost(response: Any, request_model: str | None) -> dict[str, float] | None:
    """Price one response via litellm, or None when it cannot be priced."""
    if not request_model:
        return None
    # Imported here rather than at module scope: this module is also loaded by
    # the code-executor sandbox, where paying litellm's import cost to track
    # tokens would be wasted.
    from autodiscovery import llm

    try:
        return llm.cost_of(response, request_model)
    except Exception:
        # Usage tracking is bookkeeping around a call that already succeeded.
        # An unpriceable model reports an unavailable cost, it does not fail the run.
        return None


def _delta_cost(
    model_usage: dict[str, Any],
    previous_usage: dict[str, Any],
) -> dict[str, float] | None:
    """Get the cost delta between two AG2 per-model usage summaries.

    AG2 records the per-call cost :meth:`LiteLLMAG2Client.get_usage` hands it,
    which is litellm's own figure, but only as a running total -- so this yields
    a total with no prompt/completion split, unlike the per-response path.

    Args:
        model_usage: The later AG2 usage summary for one model.
        previous_usage: The earlier summary for the same model.

    Returns:
        ``{"total_usd": delta}``, or None when the cost is unavailable.
    """
    if model_usage.get("cost") is None:
        return None
    try:
        delta = float(model_usage["cost"]) - float(previous_usage.get("cost") or 0.0)
    except (TypeError, ValueError):
        return None
    # A priced call always costs something, and this only runs for a window that
    # did consume tokens -- so a zero delta means the model is unpriced (AG2's
    # interface forced it to zero) rather than that the calls were free.
    return {"total_usd": delta} if delta > 0 else None

def _extract_usage_from_response(response: Any) -> dict[str, Any] | None:
    """Extract common usage fields from API responses."""
    usage_obj = getattr(response, "usage", None)
    if usage_obj is None and isinstance(response, dict):
        usage_obj = response.get("usage")
    if usage_obj is None:
        return None

    model = getattr(response, "model", None)
    if model is None and isinstance(response, dict):
        model = response.get("model")

    prompt_tokens = _coerce_int(_get_usage_value(usage_obj, "prompt_tokens"))
    completion_tokens = _coerce_int(_get_usage_value(usage_obj, "completion_tokens"))
    total_tokens = _coerce_int(_get_usage_value(usage_obj, "total_tokens"))
    usage_payload = _normalize_usage_payload(usage_obj)

    return {
        "model": model,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "usage": usage_payload,
    }


def _usage_payload_with_token_counts(
    *,
    usage: Any,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
) -> dict[str, Any]:
    """Create a usage payload with required token-count keys.

    Args:
        usage: Optional raw usage payload.
        prompt_tokens: Prompt token count.
        completion_tokens: Completion token count.
        total_tokens: Total token count.

    Returns:
        JSON-serializable usage payload including token counts.
    """
    normalized = _normalize_usage_payload(usage)
    payload: dict[str, Any] = {}
    if isinstance(normalized, dict):
        payload.update(normalized)
    elif normalized is not None:
        payload["raw_usage"] = normalized

    payload.setdefault("prompt_tokens", prompt_tokens)
    payload.setdefault("completion_tokens", completion_tokens)
    payload.setdefault("total_tokens", total_tokens)
    return payload


def _event_token_counts(event: dict[str, Any]) -> tuple[int, int, int]:
    """Get token counts for an event from the usage payload.

    Args:
        event: Usage event dictionary.

    Returns:
        Tuple of prompt, completion, and total token counts.
    """
    usage_obj = event.get("usage")
    prompt = _coerce_int(_get_usage_value(usage_obj, "prompt_tokens"))
    completion = _coerce_int(_get_usage_value(usage_obj, "completion_tokens"))
    total = _coerce_int(_get_usage_value(usage_obj, "total_tokens"))

    if total == 0:
        total = prompt + completion
    return prompt, completion, total


def _event_reasoning_tokens(event: dict[str, Any]) -> int:
    """Get reasoning token count for an event from usage payload.

    Args:
        event: Usage event dictionary.

    Returns:
        Number of reasoning tokens for the event.
    """
    usage_obj = event.get("usage")
    completion_details = _get_usage_value(usage_obj, "completion_tokens_details")
    reasoning = _coerce_int(_get_usage_value(completion_details, "reasoning_tokens"))
    if reasoning > 0:
        return reasoning
    return _coerce_int(_get_usage_value(usage_obj, "reasoning_tokens"))


def _normalize_usage_payload(value: Any) -> Any:
    """Normalize usage payloads into JSON-serializable Python values.

    Args:
        value: Raw usage payload (dict-like, model object, or primitive).

    Returns:
        JSON-serializable payload preserving available usage fields.
    """
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for k, v in value.items():
            normalized_value = _normalize_usage_payload(v)
            if normalized_value is not None:
                normalized[str(k)] = normalized_value
        return normalized
    if isinstance(value, (list, tuple)):
        return [_normalize_usage_payload(v) for v in value]
    if is_dataclass(value):
        return _normalize_usage_payload(asdict(value))
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            return _normalize_usage_payload(model_dump(exclude_none=True))
        except TypeError:
            return _normalize_usage_payload(model_dump())
    if hasattr(value, "__dict__"):
        normalized: dict[str, Any] = {}
        for k, v in vars(value).items():
            if k.startswith("_"):
                continue
            normalized_value = _normalize_usage_payload(v)
            if normalized_value is not None:
                normalized[k] = normalized_value
        return normalized
    return str(value)


def _get_usage_value(usage_obj: Any, key: str) -> Any:
    """Return a usage value for both dict-like and object-like usage payloads."""
    if isinstance(usage_obj, dict):
        return usage_obj.get(key)
    return getattr(usage_obj, key, None)


def _coerce_int(value: Any) -> int:
    """Convert usage value to a non-negative integer."""
    if value is None:
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _positive_delta(current: Any, previous: Any) -> int:
    """Compute positive integer delta between two numeric values."""
    current_value = _coerce_int(current)
    previous_value = _coerce_int(previous)
    delta = current_value - previous_value
    return delta if delta > 0 else 0
