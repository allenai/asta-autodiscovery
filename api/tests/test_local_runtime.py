"""Tests for provider-neutral headless local runtime behavior."""

from __future__ import annotations

import json
from pathlib import Path

from autodiscovery_jobs import JobConfig, JobManager
from flask import Flask
from runs import runs_api
from utils.experiments import ExperimentTree


def test_runtime_config_selects_local_api_upload(monkeypatch) -> None:
    monkeypatch.setenv("JOB_BACKEND", "local")
    app = Flask(__name__)
    app.register_blueprint(runs_api.create(), url_prefix="/api/runs")

    response = app.test_client().get("/api/runs/runtime-config")

    assert response.status_code == 200
    assert response.get_json() == {
        "deployment_mode": "local",
        "upload_transport": "api",
        "hosted_features": False,
    }


def test_runtime_config_preserves_hosted_default(monkeypatch) -> None:
    monkeypatch.delenv("JOB_BACKEND", raising=False)
    app = Flask(__name__)
    app.register_blueprint(runs_api.create(), url_prefix="/api/runs")

    response = app.test_client().get("/api/runs/runtime-config")

    assert response.get_json() == {
        "deployment_mode": "hosted",
        "upload_transport": "presigned",
        "hosted_features": True,
    }


def test_provider_catalog_is_sanitized(monkeypatch) -> None:
    monkeypatch.setenv("JOB_BACKEND", "local")
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "configured")
    monkeypatch.setattr(runs_api, "load_provider_credentials", lambda: None)
    monkeypatch.setattr(
        runs_api,
        "provider_configuration",
        lambda: {"openai": {"configured": False}, "vertex": {"configured": False}},
    )
    monkeypatch.setattr(
        "autodiscovery.copilot.doctor",
        lambda: {
            "status": "ready",
            "code": "READY",
            "message": "Ready",
            "remediation": None,
            "models": [{"id": "model-1", "name": "Model 1", "vision": True}],
            "account": {"authenticated": True, "label": "not-exposed"},
            "runtime": {"path": "/private/path"},
        },
    )
    app = Flask(__name__)
    app.register_blueprint(runs_api.create(), url_prefix="/api/runs")

    response = app.test_client().get("/api/runs/providers")
    payload = response.get_json()

    copilot = next(provider for provider in payload["providers"] if provider["id"] == "copilot")
    assert copilot["models"] == [{"id": "model-1", "name": "Model 1", "vision": True}]
    assert "account" not in copilot
    assert "/private/path" not in response.get_data(as_text=True)


def test_local_manager_crud_avoids_gcs(tmp_path: Path) -> None:
    manager = JobManager(JobConfig(backend="local", local_root=str(tmp_path)))

    run_path = Path(manager.create_job("local", "run-1"))
    manager.upload_metadata("local", "run-1", {"name": "Local run"})

    assert run_path == tmp_path / "runs" / "run-1"
    assert manager.list_jobs("local") == ["run-1"]
    assert manager.get_metadata("local", "run-1") == {"name": "Local run"}


def test_local_experiment_tree_reads_output(tmp_path: Path) -> None:
    config = JobConfig(backend="local", local_root=str(tmp_path))
    manager = JobManager(config)
    run_path = Path(manager.create_job("local", "run-1"))
    node = {
        "id": "node_0_1",
        "parent_id": None,
        "creation_idx": 1,
        "success": True,
        "hypothesis": "Local hypothesis",
    }
    (run_path / "output" / "mcts_node_0_1.json").write_text(
        json.dumps(node), encoding="utf-8"
    )

    tree = ExperimentTree.load("local", "run-1", config)

    assert len(tree) == 1
    assert tree.get_node("node_0_1").hypothesis == "Local hypothesis"


def test_local_copilot_cost_uses_actual_token_events(tmp_path: Path) -> None:
    output = tmp_path / "output"
    output.mkdir()
    (output / "llm_usage_events.jsonl").write_text(
        json.dumps(
            {
                "model": "claude-sonnet-4.6",
                "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 100_000},
            }
        )
        + "\nnot-json\n",
        encoding="utf-8",
    )

    estimate = runs_api._estimate_local_copilot_cost(
        tmp_path, {"llm_provider": "copilot"}
    )

    assert estimate == 4.5
