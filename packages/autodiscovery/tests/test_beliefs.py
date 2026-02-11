"""Tests for belief elicitation behavior."""

from __future__ import annotations

from autodiscovery import beliefs


def test_get_belief_preserves_reasoning_for_gemini(monkeypatch) -> None:
    """Ensure Gemini belief calls keep configured reasoning effort."""
    captured: dict[str, str | None] = {"reasoning_effort": None}

    def _fake_query_llm(messages, **kwargs):
        _ = messages
        captured["reasoning_effort"] = kwargs.get("reasoning_effort")
        return [{"belief": True}]

    monkeypatch.setattr(beliefs, "query_llm", _fake_query_llm)

    distr, mean = beliefs.get_belief(
        hypothesis="Example hypothesis.",
        model="gemini-3-flash-preview",
        belief_mode="boolean",
        n_samples=1,
        reasoning_effort="high",
        use_llm_prior=True,
    )

    assert distr is not None
    assert mean is not None
    assert captured["reasoning_effort"] == "high"


def test_get_belief_preserves_reasoning_for_non_gemini(monkeypatch) -> None:
    """Ensure non-Gemini belief calls keep configured reasoning effort."""
    captured: dict[str, str | None] = {"reasoning_effort": None}

    def _fake_query_llm(messages, **kwargs):
        _ = messages
        captured["reasoning_effort"] = kwargs.get("reasoning_effort")
        return [{"belief": True}]

    monkeypatch.setattr(beliefs, "query_llm", _fake_query_llm)

    distr, mean = beliefs.get_belief(
        hypothesis="Example hypothesis.",
        model="gpt-4o",
        belief_mode="boolean",
        n_samples=1,
        reasoning_effort="high",
        use_llm_prior=True,
    )

    assert distr is not None
    assert mean is not None
    assert captured["reasoning_effort"] == "high"
