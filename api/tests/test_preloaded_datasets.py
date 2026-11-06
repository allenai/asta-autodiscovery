"""Preloaded datasets come only from the API's registry, for any signed-in user."""

from unittest.mock import patch

import pytest

# Flask is an api/ dependency, not a workspace one: `make test` layers in
# api/requirements.txt, but a bare `uv run pytest` skips this module.
flask = pytest.importorskip("flask")

from auth import auth_api  # noqa: E402
from autodiscovery_jobs import JobManager  # noqa: E402
from autodiscovery_jobs.persistence import dataset_key  # noqa: E402
from runs import runs_api  # noqa: E402
from runs.preloaded_datasets import PRELOADED_DATASETS  # noqa: E402
from utils.auth import reset_auth_provider  # noqa: E402
from utils.auth.password_store import PasswordStore  # noqa: E402

USER_ID = "file|alice"
HEART = PRELOADED_DATASETS["tabula-sapiens-heart"]


@pytest.fixture
def store_dir(tmp_path):
    return tmp_path / "store"


@pytest.fixture
def client(tmp_path, store_dir, monkeypatch):
    """The runs API behind password_file."""
    passwords = tmp_path / "passwords"
    passwords.mkdir()
    PasswordStore.in_dir(passwords).add_user("alice", "alice-password")
    monkeypatch.setenv("AUTH_PROVIDER", "password_file")
    monkeypatch.setenv("AUTH_PASSWORD_DIR", str(passwords))
    monkeypatch.setenv("AUTH_SESSION_SECRET", "session-secret-" + "x" * 32)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(store_dir))
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
    """A signed-in user holding no permissions."""
    response = client.post(
        "/api/auth/login", json={"username": "alice", "password": "alice-password"}
    )
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def _new_run(client, alice) -> str:
    return client.post("/api/runs/create", headers=alice).get_json()["runid"]


def _submit(client, alice, runid):
    # No experiment count: a submit that gets past the datasets stops at
    # validation with a 400, before any job is launched.
    with patch.object(runs_api, "sync_preloaded_dataset") as sync:
        response = client.post("/api/runs/submit", headers=alice, json={"runid": runid})
    return response, sync


def _submit_with_dataset(client, alice, dataset: dict):
    runid = _new_run(client, alice)
    JobManager().upload_metadata(USER_ID, runid, {"name": "Run", "datasets": [dataset]})
    return (runid, *_submit(client, alice, runid))


def _assert_copied(sync, runid):
    sync.assert_called_once()
    assert sync.call_args.kwargs["source_gs_url"] == HEART.source
    assert sync.call_args.kwargs["dest_key"] == dataset_key(USER_ID, runid, HEART.filename)


@pytest.mark.parametrize(
    "dataset",
    [
        {"preloaded_id": HEART.id},
        {"name": HEART.filename, "url": HEART.source},  # saved before ids
    ],
    ids=["by-id", "by-legacy-url"],
)
def test_a_preloaded_dataset_is_copied_without_any_permission(client, alice, dataset):
    runid, response, sync = _submit_with_dataset(client, alice, dataset)
    _assert_copied(sync, runid)
    assert response.status_code == 400
    assert "Number of Experiments" in response.get_json()["error"]


def test_the_registry_decides_the_source_and_filename(client, alice):
    runid, _, sync = _submit_with_dataset(
        client,
        alice,
        {
            "preloaded_id": HEART.id,
            "name": "../../other/data/heart.h5ad",
            "url": "gs://another-bucket/data.h5ad",
        },
    )
    _assert_copied(sync, runid)


@pytest.mark.parametrize(
    "dataset",
    [
        {"preloaded_id": "no-such-dataset"},
        {"url": f"{HEART.source}.bak"},
        {"url": HEART.source.rsplit("/", 1)[0] + "/other.h5ad"},
        {"url": "gs://another-bucket/data.h5ad"},
    ],
)
def test_any_other_preloaded_dataset_is_refused(client, alice, dataset):
    _, response, sync = _submit_with_dataset(client, alice, dataset)
    sync.assert_not_called()
    assert response.status_code == 400


def test_saving_metadata_spells_out_a_preloaded_dataset(client, alice):
    runid = _new_run(client, alice)
    response = client.post(
        f"/api/runs/{runid}/metadata",
        headers=alice,
        json={"metadata": {"name": "Run", "datasets": [{"preloaded_id": HEART.id}]}},
    )
    assert response.status_code == 200
    [saved] = JobManager().get_metadata(USER_ID, runid)["datasets"]
    assert saved["preloaded_id"] == HEART.id
    assert saved["name"] == HEART.filename
    assert saved["url"] == HEART.source
    assert saved["is_preloaded"] is True


def test_saving_metadata_refuses_an_unknown_preloaded_dataset(client, alice):
    runid = _new_run(client, alice)
    response = client.post(
        f"/api/runs/{runid}/metadata",
        headers=alice,
        json={"metadata": {"name": "Run", "datasets": [{"url": "gs://another-bucket/x"}]}},
    )
    assert response.status_code == 400


def test_a_fork_of_a_sample_run_on_a_preloaded_dataset_submits(client, alice, store_dir):
    manager = JobManager()
    manager.create_job("samples", "sample-run")
    manager.upload_metadata(
        "samples",
        "sample-run",
        {"name": "Sample", "datasets": [{"name": HEART.filename, "url": HEART.source}]},
    )
    copied = store_dir / dataset_key("samples", "sample-run", HEART.filename)
    copied.parent.mkdir(parents=True, exist_ok=True)
    copied.write_bytes(b"h5ad")

    forked = client.post("/api/runs/fork", headers=alice, json={"parent_run_id": "sample-run"})
    assert forked.status_code == 200, forked.get_json()
    runid = forked.get_json()["runid"]

    response, sync = _submit(client, alice, runid)
    _assert_copied(sync, runid)
    assert response.status_code == 400
    assert "Number of Experiments" in response.get_json()["error"]
