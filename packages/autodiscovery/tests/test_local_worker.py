"""Tests for the local engine/report wrapper."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from autodiscovery import local_worker


def test_local_worker_runs_engine_and_report(monkeypatch, tmp_path: Path) -> None:
    """Delegate to the existing engine before generating its static report."""
    args = SimpleNamespace(
        out_dir=str(tmp_path / "output"),
        work_dir=str(tmp_path / "work"),
        delete_work_dir=False,
        n_experiments=0,
    )
    calls = []
    monkeypatch.setattr(
        local_worker,
        "ArgParser",
        lambda: SimpleNamespace(parse_args=lambda argv: args),
    )
    monkeypatch.setattr(local_worker, "run_main", lambda parsed: calls.append(("run", parsed)))
    monkeypatch.setattr(
        local_worker,
        "generate_report",
        lambda out_dir: calls.append(("report", out_dir)),
    )
    monkeypatch.setattr(
        local_worker,
        "validate_run_completion",
        lambda out_dir, requested: calls.append(("validate", (out_dir, requested))),
    )
    monkeypatch.setattr(
        local_worker,
        "close_copilot_runtime",
        lambda: calls.append(("close", None)),
    )

    result = local_worker.main(["--ignored"])

    assert result == 0
    assert calls == [
        ("run", args),
        ("report", args.out_dir),
        ("validate", (args.out_dir, 0)),
        ("close", None),
    ]


def test_completion_validation_rejects_failed_substantive_node(tmp_path: Path) -> None:
    """Do not report process success when belief/reward marked the experiment failed."""
    output = tmp_path / "output"
    output.mkdir()
    (output / "mcts_nodes.json").write_text(
        '[{"hypothesis": null, "success": true}, {"hypothesis": "H", "success": false}]',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="0 of 1 requested"):
        local_worker.validate_run_completion(str(output), 1)


def test_completion_validation_accepts_requested_successes(tmp_path: Path) -> None:
    """Accept runs that completed the requested substantive experiment budget."""
    output = tmp_path / "output"
    output.mkdir()
    (output / "mcts_nodes.json").write_text(
        '[{"hypothesis": null, "success": true}, {"hypothesis": "H", "success": true}]',
        encoding="utf-8",
    )

    local_worker.validate_run_completion(str(output), 1)
