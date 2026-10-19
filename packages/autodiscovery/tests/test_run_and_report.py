"""Tests for the engine entry point that runs AutoDiscovery and writes its report."""

from pathlib import Path
from types import SimpleNamespace

from autodiscovery import run


def test_run_and_report_reports_on_the_results_dir(monkeypatch, tmp_path: Path) -> None:
    """Run the engine, then generate the report from the directory it wrote to."""
    results_dir = tmp_path / "output" / "20260101-000000"
    args = SimpleNamespace(out_dir=str(tmp_path / "output"))
    calls = []
    monkeypatch.setattr(
        run, "main", lambda parsed: calls.append(("run", parsed)) or str(results_dir)
    )
    monkeypatch.setattr(
        run, "generate_report", lambda out_dir: calls.append(("report", out_dir)) or ""
    )

    run.run_and_report(args)

    assert calls == [("run", args), ("report", str(results_dir))]


def test_run_and_report_keeps_results_when_the_report_fails(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    """A report failure is a warning, not a failed run."""

    def fail(out_dir: str) -> str:
        raise ValueError("no nodes")

    monkeypatch.setattr(run, "main", lambda parsed: str(tmp_path))
    monkeypatch.setattr(run, "generate_report", fail)

    run.run_and_report(SimpleNamespace(out_dir=str(tmp_path)))

    assert "could not generate HTML report: no nodes" in capsys.readouterr().out


def test_report_is_written_from_engine_output(tmp_path: Path) -> None:
    """The real report generator accepts the engine's aggregate node file."""
    (tmp_path / "mcts_nodes.json").write_text(
        '[{"id": "node_0_0", "hypothesis": null, "success": true}]', encoding="utf-8"
    )

    index = Path(run.generate_report(str(tmp_path)))

    assert index == tmp_path / "report" / "index.html"
    assert (tmp_path / "report" / "data.js").is_file()
