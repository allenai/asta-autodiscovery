"""Tests for the slime surprisal-reward integration (no LLM or network calls)."""

import asyncio
import json

import autodiscovery.slime_reward as slime_reward
import pytest
from autodiscovery.slime_reward import (
    SurpriseRewardConfig,
    SurpriseRewardScorer,
    _DatasetRouter,
    _load_registry,
    compute_reward,
)


@pytest.fixture
def metadata_path(tmp_path):
    """A tiny asta-format dataset + metadata.json on disk."""
    (tmp_path / "data.csv").write_text("a,b\n1,2\n3,4\n")
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps(
            {
                "description": "Toy dataset",
                "datasets": [{"name": "data.csv", "description": "two columns"}],
            }
        )
    )
    return str(metadata)


def _make_scorer(metadata_path, tmp_path, **overrides):
    config = SurpriseRewardConfig(
        dataset_metadata=metadata_path,
        work_dir=str(tmp_path / "work"),
        run_data_loading=False,  # skip the warmup experiment in tests
        reward_mode="belief",
        use_binary_reward=False,
        surprisal_width=0.2,
        **overrides,
    )
    return SurpriseRewardScorer(config)


def _fake_chat_messages(query, reviewer_success=True):
    """Messages as they come back from a completed experiment group chat."""
    return [
        {"name": "user_proxy", "role": "user", "content": query},
        {
            "name": "experiment_programmer",
            "role": "user",
            "content": json.dumps({"code": "print(1)"}),
        },
        {"name": "code_executor", "role": "user", "content": "1"},
        {
            "name": "experiment_code_analyst",
            "role": "user",
            "content": json.dumps({"success": True, "analysis": "Looks fine."}),
        },
        {
            "name": "experiment_reviewer",
            "role": "user",
            "content": json.dumps({"success": reviewer_success, "feedback": "ok"}),
        },
    ]


class _FakeDistribution:
    def __init__(self, mean):
        self.mean = mean

    def get_mean_belief(self, prior=None, recompute=False):
        return self.mean


def _stub_pipeline(scorer, monkeypatch, reviewer_success=True):
    """Stub the planner, group chat, and belief calls of *scorer*."""
    plan = {"objective": "o", "steps": "s", "deliverables": "d"}
    monkeypatch.setattr(
        scorer, "_plan", lambda hypothesis: {"hypothesis": hypothesis, "experiment_plan": plan}
    )
    monkeypatch.setattr(
        scorer, "_run_chat", lambda query: _fake_chat_messages(query, reviewer_success)
    )
    monkeypatch.setattr(
        slime_reward,
        "calculate_prior_and_posterior_beliefs",
        lambda node, **kwargs: (_FakeDistribution(0.5), _FakeDistribution(0.9), 0.4, 1.0),
    )


# -- scorer -------------------------------------------------------------------


def test_score_returns_surprisal_scalar(metadata_path, tmp_path, monkeypatch):
    """Hypothesis in -> scalar surprisal reward out, matching get_self_value."""
    scorer = _make_scorer(metadata_path, tmp_path)
    _stub_pipeline(scorer, monkeypatch)

    result = scorer.score("Taller plants produce more seeds.")

    assert result["success"] is True
    # reward_mode="belief", continuous: belief_change / surprisal_width
    assert result["reward"] == pytest.approx(0.4 / 0.2)
    assert result["surprising"] is True
    assert result["belief_change"] == pytest.approx(0.4)
    assert result["hypothesis"] == "Taller plants produce more seeds."


def test_failed_experiment_returns_failed_reward(metadata_path, tmp_path, monkeypatch):
    """A rejected experiment yields the configured failure reward, not a crash."""
    scorer = _make_scorer(metadata_path, tmp_path, failed_reward=-1.0)
    _stub_pipeline(scorer, monkeypatch, reviewer_success=False)

    result = scorer.score("A hypothesis whose experiment fails.")

    assert result["success"] is False
    assert result["reward"] == -1.0
    assert result["error"] is not None


def test_compute_reward_returns_scalar(monkeypatch):
    """The package-level entry point returns a plain float for a hypothesis."""

    class StubScorer:
        def score(self, hypothesis, experiment_plan=None):
            assert hypothesis == "My hypothesis"
            return {"reward": 1.5, "success": True}

    monkeypatch.setattr(slime_reward, "get_scorer", lambda config=None: StubScorer())

    reward = compute_reward("My hypothesis")
    assert isinstance(reward, float)
    assert reward == 1.5


# -- multi-dataset router -----------------------------------------------------


def test_router_routes_and_dedupes(metadata_path, monkeypatch):
    """The server router picks the dataset's scorer and memoizes request_ids."""
    calls = []

    class StubScorer:
        def __init__(self, config):
            self.config = config

        def score(self, hypothesis, experiment_plan=None):
            calls.append((self.config.dataset_metadata, hypothesis))
            return {"reward": 2.0, "success": True, "hypothesis": hypothesis}

    monkeypatch.setattr(slime_reward, "SurpriseRewardScorer", StubScorer)
    base = SurpriseRewardConfig(dataset_metadata=metadata_path)
    router = _DatasetRouter(base, registry={"toy": metadata_path}, concurrency=1)

    payload = {"hypothesis": "H", "dataset_id": "toy", "request_id": "req-1"}
    first = router.score(payload)
    second = router.score(payload)  # HTTP retry: must not re-run the experiment

    assert first["reward"] == 2.0
    assert first["dataset_id"] == "toy"
    assert second == first
    assert calls == [(metadata_path, "H")]

    # A fresh request_id is not served from the cache: the scorer runs again.
    router.score({"hypothesis": "H", "dataset_id": "toy", "request_id": "req-2"})
    assert len(calls) == 2

    with pytest.raises(KeyError):
        router.score({"hypothesis": "H", "dataset_id": "unknown"})


def test_router_omitted_dataset_id_uses_single(metadata_path, monkeypatch):
    """With exactly one registered dataset, dataset_id may be omitted."""
    seen = []

    class StubScorer:
        def __init__(self, config):
            self.config = config

        def score(self, hypothesis, experiment_plan=None):
            seen.append(self.config.dataset_metadata)
            return {"reward": 0.0, "success": True}

    monkeypatch.setattr(slime_reward, "SurpriseRewardScorer", StubScorer)
    base = SurpriseRewardConfig(dataset_metadata=metadata_path)
    router = _DatasetRouter(base, registry={"only": metadata_path}, concurrency=1)

    result = router.score({"hypothesis": "H"})
    assert result["dataset_id"] == "only"
    assert seen == [metadata_path]


def test_router_score_is_thread_safe_scalar(metadata_path, monkeypatch):
    """Concurrent requests each get their own scalar result."""

    class StubScorer:
        def __init__(self, config):
            self.config = config

        def score(self, hypothesis, experiment_plan=None):
            return {"reward": float(len(hypothesis)), "success": True}

    monkeypatch.setattr(slime_reward, "SurpriseRewardScorer", StubScorer)
    base = SurpriseRewardConfig(dataset_metadata=metadata_path)
    router = _DatasetRouter(base, registry={"toy": metadata_path}, concurrency=2)

    async def _gather():
        return await asyncio.gather(
            *(
                asyncio.to_thread(router.score, {"hypothesis": "x" * n, "dataset_id": "toy"})
                for n in (1, 2, 3)
            )
        )

    results = asyncio.run(_gather())
    assert sorted(r["reward"] for r in results) == [1.0, 2.0, 3.0]


# -- registry loading ---------------------------------------------------------


def test_load_registry_merges_file_and_single(tmp_path):
    reg_file = tmp_path / "registry.json"
    reg_file.write_text(json.dumps({"a": "/data/a/metadata.json"}))
    registry = _load_registry(str(reg_file), "/data/single/metadata.json")
    assert registry == {"a": "/data/a/metadata.json", "default": "/data/single/metadata.json"}

    with pytest.raises(ValueError):
        _load_registry(None, None)
