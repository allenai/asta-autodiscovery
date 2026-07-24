"""Launch the surprisal reward server with the LLM+sandbox scorer stubbed out.

This exercises the *real* routing / dedup / HTTP / registry code paths from
``autodiscovery.slime_reward`` (``_DatasetRouter``, ``serve``, ``cli_main``);
only ``SurpriseRewardScorer`` is swapped for a deterministic ``MockScorer``, so
it needs no models, GPUs, sandbox, or GCP. Use it to smoke-test the slime reward
wiring in a Beaker session before spending LLM/GPU budget on the real thing.

Run it exactly like the real server (same flags), e.g.::

    uv run python scripts/slime/mock_reward_server.py \
        --dataset_registry /tmp/registry.json --host 127.0.0.1 --port 8137

Registry paths need not exist: the mock scorer never opens the datasets.
"""

from __future__ import annotations

import hashlib
import threading

import autodiscovery.slime_reward as slime_reward

_calls = {"n": 0}
_calls_lock = threading.Lock()


class MockScorer:
    """Deterministic stand-in for ``SurpriseRewardScorer`` (no LLM / sandbox)."""

    def __init__(self, config):
        self.config = config

    def score(self, hypothesis: str, experiment_plan=None) -> dict:
        with _calls_lock:
            _calls["n"] += 1
            call_index = _calls["n"]
        # Deterministic pseudo prior/posterior in [0, 1] from the hypothesis text
        # so the same hypothesis always yields the same reward.
        digest = int(hashlib.sha256(hypothesis.encode()).hexdigest(), 16)
        prior = (digest % 1000) / 1000.0
        posterior = ((digest // 1000) % 1000) / 1000.0
        belief_change = abs(posterior - prior)
        width = self.config.surprisal_width or 0.2
        return {
            "reward": float(belief_change / width),
            "success": True,
            "surprising": belief_change > width,
            "belief_change": belief_change,
            "kl_divergence": belief_change * 2.0,
            "prior_mean": prior,
            "posterior_mean": posterior,
            "hypothesis": hypothesis,
            "error": None,
            # Test hooks: prove dedup (same request_id -> same call_index) and
            # that this is the stub, not the real scorer.
            "mock": True,
            "call_index": call_index,
        }


def main() -> None:
    # Swap in the stub, then reuse the real CLI (arg parsing, registry, serve).
    slime_reward.SurpriseRewardScorer = MockScorer
    slime_reward.cli_main()


if __name__ == "__main__":
    main()
