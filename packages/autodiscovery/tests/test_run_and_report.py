"""Tests for the engine entry point that runs AutoDiscovery and writes its report."""

import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from autodiscovery import report, run


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


def _report_data(report_dir: Path) -> dict:
    text = (report_dir / "data.js").read_text(encoding="utf-8")
    prefix = "window.AUTODISCOVERY_REPORT = "
    assert text.startswith(prefix)
    return json.loads(text[len(prefix) :].rstrip().rstrip(";"))


@pytest.fixture
def viewer(monkeypatch, tmp_path: Path) -> Path:
    """Stand in for the built run view, which a plain Python checkout lacks."""
    page = tmp_path / "viewer" / "index.html"
    page.parent.mkdir()
    page.write_text("<!doctype html><title>viewer</title>", encoding="utf-8")
    monkeypatch.setattr(report, "VIEWER_HTML", page)
    return page


def test_report_is_written_from_engine_output(tmp_path: Path, viewer: Path) -> None:
    """The real report generator accepts the engine's aggregate node file."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "mcts_nodes.json").write_text(
        '[{"id": "node_0_0", "hypothesis": null, "success": true}]', encoding="utf-8"
    )

    index = Path(run.generate_report(str(out)))

    assert index == out / "report" / "index.html"
    assert index.read_text(encoding="utf-8") == viewer.read_text(encoding="utf-8")
    assert _report_data(out / "report")["experiments"][0]["experiment_id"] == "node_0_0"


def test_report_carries_the_run_as_the_api_serves_it(tmp_path: Path, viewer: Path) -> None:
    """data.js holds the run and experiments in the API's shapes, figures as files."""
    out = tmp_path / "out"
    (out / "rich_outputs").mkdir(parents=True)
    metadata = tmp_path / "metadata.json"
    metadata.write_text(
        json.dumps({"name": "Pets", "datasets": [{"name": "pets.csv", "description": "d"}]}),
        encoding="utf-8",
    )
    (out / "args.json").write_text(
        json.dumps(
            {
                "dataset_metadata": str(metadata),
                "n_experiments": 2,
                "surprisal_width": 0.2,
                "datalib_dir": ["/data/lib/very cool data"],
            }
        ),
        encoding="utf-8",
    )
    (out / "mcts_nodes.json").write_text(
        json.dumps(
            [
                {"id": "node_1_0", "parent_id": None, "creation_idx": 1, "success": True},
                {
                    "id": "node_2_0",
                    "parent_id": "node_1_0",
                    "creation_idx": 2,
                    "success": True,
                    "surprising": True,
                    "hypothesis": "h",
                    "prior": {"mean": 0.25},
                    "posterior": {"mean": 0.75},
                    "time_elapsed": 2.5,
                    "code": "print(1)",
                    "created_at": "2026-01-01T00:00:00+00:00",
                },
            ]
        ),
        encoding="utf-8",
    )
    png = base64.b64encode(b"png-bytes").decode()
    (out / "rich_outputs" / "ro_2_0.json").write_text(
        json.dumps([{"image/png": png}, {"text/plain": "table"}, {"application/x": "?"}]),
        encoding="utf-8",
    )

    run.generate_report(str(out))

    data = _report_data(out / "report")
    root, exp = data["experiments"]
    assert root["child_ids"] == ["node_2_0"]
    assert exp["id_in_run"] == 1
    assert exp["status"] == "SUCCEEDED"
    assert (exp["prior"], exp["posterior"], exp["runtime_ms"]) == (0.25, 0.75, 2500.0)
    assert exp["code"] == "print(1)"
    # Positions are kept, so figure numbers line up with the web UI's.
    assert exp["rich_outputs"] == [
        {"x-report-figure-url": "figures/node_2_0_0.png"},
        {"text/plain": "table"},
        {},
    ]
    assert (out / "report" / "figures" / "node_2_0_0.png").read_bytes() == b"png-bytes"

    run_data = data["run"]
    assert run_data["name"] == "Pets"
    assert run_data["run_details"]["status"] == "SUCCEEDED"
    assert run_data["run_details"]["created_at"] == "2026-01-01T00:00:00+00:00"
    assert run_data["run_stats"]["requested_experiments"] == 2
    assert run_data["run_stats"]["num_surprising_experiments"] == 1
    assert run_data["run_metadata"]["surprisal_width"] == 0.2
    assert run_data["run_metadata"]["datalib_dirs"] == ["very cool data"]
    assert run_data["run_metadata"]["datasets"][0]["name"] == "pets.csv"


def test_report_without_a_built_viewer_keeps_the_data(monkeypatch, tmp_path: Path) -> None:
    """A checkout that never built the viewer gets data.js and a pointer to the fix."""
    monkeypatch.setattr(report, "VIEWER_HTML", tmp_path / "missing" / "index.html")
    (tmp_path / "mcts_nodes.json").write_text("[]", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="make report-viewer"):
        run.generate_report(str(tmp_path))

    assert (tmp_path / "report" / "data.js").is_file()
    assert not (tmp_path / "report" / "index.html").exists()
