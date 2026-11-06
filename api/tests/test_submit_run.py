"""Responses from the run-submit endpoint, and what it hands the job."""

from unittest.mock import patch

import pytest

# Flask is an api/ dependency, not a workspace one: `make test` layers in
# api/requirements.txt, but a bare `uv run pytest` skips this module.
flask = pytest.importorskip("flask")

from autodiscovery_jobs import JobManager  # noqa: E402
from runs import runs_api  # noqa: E402


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A runs API for the single local user, on a local store under ``tmp_path``."""
    monkeypatch.setenv("AUTH_PROVIDER", "none")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("JOB_BACKEND", "docker")
    monkeypatch.setenv("AUTODISCOVERY_IMAGE", "autodiscovery:test")
    app = flask.Flask(__name__)
    app.register_blueprint(runs_api.create(), url_prefix="/api/runs")
    return app.test_client()


def test_submit_without_an_experiment_count_is_a_bad_request(client):
    """A validation BadRequest is the client's error, not the catch-all's 500."""
    manager = JobManager()
    manager.create_job("local", "run-1")
    manager.upload_metadata("local", "run-1", {"name": "No count", "datasets": []})

    response = client.post("/api/runs/submit", json={"runid": "run-1", "userid": "local"})

    assert response.status_code == 400
    assert "Number of Experiments" in response.get_json()["error"]


def test_a_stored_warmstart_path_is_not_passed_to_the_job(client, tmp_path):
    """warmstart_experiments names a path on the job's filesystem: the API never forwards it."""
    manager = JobManager()
    manager.create_job("local", "run-1")
    (tmp_path / "data.csv").write_text("a\n1\n")
    manager.upload_dataset("local", "run-1", str(tmp_path / "data.csv"))
    manager.upload_metadata(
        "local",
        "run-1",
        {
            "name": "Seeded",
            "datasets": [{"name": "data.csv"}],
            "n_experiments": 4,
            "warmstart_experiments": "/somewhere/seeds.json",
            "n_warmstart": 2,
        },
    )

    with (
        patch.object(runs_api, "check_experiment_limits"),
        patch.object(JobManager, "run_job", return_value="exec-1") as run_job,
    ):
        client.post("/api/runs/submit", json={"runid": "run-1"})

    run_job.assert_called_once()
    assert "warmstart_experiments" not in run_job.call_args.kwargs
    assert run_job.call_args.kwargs["n_warmstart"] == 2
