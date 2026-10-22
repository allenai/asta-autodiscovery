"""Error responses from the run-submit endpoint."""

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
