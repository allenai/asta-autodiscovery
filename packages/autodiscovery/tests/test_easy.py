"""Tests for the simplified ``auto-discovery`` CLI."""

from __future__ import annotations

import pytest
from autodiscovery import easy, run
from autodiscovery.args import ArgParser


def test_engine_namespace_sets_every_engine_argument(tmp_path, monkeypatch):
    """The CLI builds run.main()'s Namespace by hand, so it must keep up with ArgParser."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    captured = []
    monkeypatch.setattr(run, "run_and_report", captured.append)
    dataset = tmp_path / "d.csv"
    dataset.write_text("a,b\n1,2\n")

    easy.cli_main(
        [
            "--model",
            "openai/gpt-4o",
            "--n_experiments",
            "1",
            "--out_dir",
            str(tmp_path / "out"),
            str(dataset),
        ]
    )

    (engine_args,) = captured
    expected = {action.dest for action in ArgParser()._actions if action.dest != "help"}
    missing = expected - set(vars(engine_args))
    if missing:
        pytest.fail(f"auto-discovery does not set engine arguments: {sorted(missing)}")
