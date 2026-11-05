"""Submit copies in a gs:// dataset only when it is one of the preloaded ones."""

from unittest.mock import patch

import pytest

# Flask is an api/ dependency, not a workspace one: `make test` layers in
# api/requirements.txt, but a bare `uv run pytest` skips this module.
flask = pytest.importorskip("flask")

from auth import auth_api  # noqa: E402
from autodiscovery_jobs import JobManager  # noqa: E402
from runs import runs_api  # noqa: E402
from runs.preloaded_datasets import PRELOADED_DATASET_URLS  # noqa: E402
from utils.auth import reset_auth_provider  # noqa: E402
from utils.auth.password_store import PasswordStore  # noqa: E402

USER_ID = "file|alice"
PRELOADED = sorted(PRELOADED_DATASET_URLS)[0]


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The runs API behind password_file, for a user holding no permissions."""
    passwords = tmp_path / "passwords"
    passwords.mkdir()
    PasswordStore.in_dir(passwords).add_user("alice", "alice-password")
    monkeypatch.setenv("AUTH_PROVIDER", "password_file")
    monkeypatch.setenv("AUTH_PASSWORD_DIR", str(passwords))
    monkeypatch.setenv("AUTH_SESSION_SECRET", "session-secret-" + "x" * 32)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("JOB_BACKEND", "docker")
    monkeypatch.setenv("AUTODISCOVERY_IMAGE", "autodiscovery:test")
    reset_auth_provider()
    app = flask.Flask(__name__)
    app.register_blueprint(runs_api.create(), url_prefix="/api/runs")
    app.register_blueprint(auth_api.create(), url_prefix="/api/auth")
    yield app.test_client()
    reset_auth_provider()


@pytest.fixture
def alice(client) -> dict:
    response = client.post(
        "/api/auth/login", json={"username": "alice", "password": "alice-password"}
    )
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def _submit_with_dataset(client, alice, url):
    runid = client.post("/api/runs/create", headers=alice).get_json()["runid"]
    # No experiment count: a submit that gets past the dataset check stops at
    # validation with a 400, before any job is launched.
    JobManager().upload_metadata(
        USER_ID, runid, {"name": "Run", "datasets": [{"name": "data.h5ad", "url": url}]}
    )
    with patch.object(runs_api, "sync_preloaded_dataset") as sync:
        response = client.post("/api/runs/submit", headers=alice, json={"runid": runid})
    return response, sync


def test_a_preloaded_dataset_is_copied_without_any_permission(client, alice):
    response, sync = _submit_with_dataset(client, alice, PRELOADED)
    sync.assert_called_once()
    assert sync.call_args.kwargs["source_gs_url"] == PRELOADED
    assert response.status_code == 400
    assert "Number of Experiments" in response.get_json()["error"]


@pytest.mark.parametrize(
    "url",
    [
        f"{PRELOADED}.bak",
        PRELOADED.rsplit("/", 1)[0] + "/other.h5ad",
        "gs://another-bucket/data.h5ad",
    ],
)
def test_any_other_gs_url_is_refused(client, alice, url):
    response, sync = _submit_with_dataset(client, alice, url)
    sync.assert_not_called()
    assert response.status_code == 403
    assert "not one of the preloaded datasets" in response.get_json()["error"]
