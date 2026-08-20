"""Aggregate experiment metrics for AutoDiscovery runs.

One ``RunMetrics`` instance accumulates the key health metrics of a run —
% execution failures, % surprising hypotheses, token usage, and the configured
per-message token limit — and renders them as a compact log line after every
experiment plus a ``run_metrics.json`` summary. Shared by the standalone engine
(``autodiscovery.run``) and the slime reward server
(``autodiscovery.slime_reward``) so both paths report the same numbers the same
way.
"""

from __future__ import annotations

import json
import os
import threading

# Per-message token cap applied to every AG2 agent. Defined here (not in
# agents.py) so the metrics logger can report the limit without importing the
# heavy agents module; agents.py imports these for its MessageTokenLimiter.
MAX_TOKENS_PER_MESSAGE = 16_384
MIN_TOKENS = 20_000
TOKEN_LIMIT = {
    "max_tokens_per_message": MAX_TOKENS_PER_MESSAGE,
    "min_tokens": MIN_TOKENS,
}


class RunMetrics:
    """Thread-safe counters over the experiments of one run / server process.

    ``record()`` after every experiment attempt (including ones that raised).
    ``surprising`` is tri-state: None means the experiment was never belief-
    scored (execution failure), so surprise rate is reported over scored
    experiments only.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.n_experiments = 0
        self.n_exec_failures = 0
        self.n_scored = 0
        self.n_surprising = 0

    def record(self, *, success: bool, surprising: bool | None) -> None:
        with self._lock:
            self.n_experiments += 1
            if not success:
                self.n_exec_failures += 1
            if surprising is not None:
                self.n_scored += 1
                if surprising:
                    self.n_surprising += 1

    def snapshot(self, usage_tracker=None) -> dict:
        """Current metrics as a dict; merges token totals from *usage_tracker*."""
        with self._lock:
            n, fails = self.n_experiments, self.n_exec_failures
            scored, surprising = self.n_scored, self.n_surprising
        snap = {
            "n_experiments": n,
            "n_exec_failures": fails,
            "pct_exec_failures": round(100.0 * fails / n, 1) if n else None,
            "n_scored": scored,
            "n_surprising": surprising,
            "pct_surprising_of_scored": round(100.0 * surprising / scored, 1) if scored else None,
            "pct_surprising_of_all": round(100.0 * surprising / n, 1) if n else None,
            "token_limit": TOKEN_LIMIT,
        }
        if usage_tracker is not None:
            snap["token_usage"] = usage_tracker.get_summary().get("totals", {})
        return snap

    def log_line(self, usage_tracker=None, prefix: str = "[metrics]") -> str:
        """One-line summary for stdout, emitted after every experiment."""
        s = self.snapshot(usage_tracker)
        pf = "n/a" if s["pct_exec_failures"] is None else f"{s['pct_exec_failures']}%"
        ps = (
            "n/a"
            if s["pct_surprising_of_scored"] is None
            else f"{s['pct_surprising_of_scored']}%"
        )
        line = (
            f"{prefix} experiments={s['n_experiments']} "
            f"exec_failures={s['n_exec_failures']} ({pf}) "
            f"surprising={s['n_surprising']}/{s['n_scored']} scored ({ps})"
        )
        usage = s.get("token_usage")
        if usage:
            line += (
                f" | tokens prompt={usage.get('prompt_tokens', 0):,}"
                f" completion={usage.get('completion_tokens', 0):,}"
                f" total={usage.get('total_tokens', 0):,}"
                f" calls={usage.get('calls', 0):,}"
            )
        line += (
            f" | token_limit={MAX_TOKENS_PER_MESSAGE:,}/msg (min_tokens={MIN_TOKENS:,})"
        )
        return line

    def save(self, log_dirname: str, usage_tracker=None, filename: str = "run_metrics.json") -> str:
        """Write the snapshot to ``<log_dirname>/run_metrics.json``; returns the path."""
        os.makedirs(log_dirname, exist_ok=True)
        path = os.path.join(log_dirname, filename)
        with open(path, "w") as f:
            json.dump(self.snapshot(usage_tracker), f, indent=2)
        return path
