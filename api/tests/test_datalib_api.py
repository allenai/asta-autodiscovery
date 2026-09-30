"""Data-library endpoints: listing a user's directories and checking them on submit."""

from unittest.mock import MagicMock, patch

import pytest

# Flask is an api/ dependency, not a workspace one, so `make test` skips this module.
flask = pytest.importorskip("flask")

from autodiscovery_jobs import DatalibDir  # noqa: E402
from runs import runs_api  # noqa: E402
from user import user_api  # noqa: E402
from utils.auth.models import AuthenticatedUser  # noqa: E402


@pytest.fixture
def manager():
    return MagicMock()


@pytest.fixture
def client(manager):
    provider = MagicMock()
    provider.authenticate.return_value = AuthenticatedUser(sub="u1", permissions=[])
    app = flask.Flask(__name__)
    app.register_blueprint(user_api.create(), url_prefix="/api/user")
    app.register_blueprint(runs_api.create(), url_prefix="/api/runs")
    with (
        patch("utils.auth.decorators.get_auth_provider", return_value=provider),
        patch.object(user_api, "JobManager", return_value=manager),
        patch.object(runs_api, "JobManager", return_value=manager),
        patch.object(runs_api, "check_experiment_limits"),
        patch.object(runs_api, "update_run_details"),
        patch.object(runs_api, "get_run_details", return_value=None),
    ):
        yield app.test_client()


def test_list_datalib(client, manager):
    manager.list_datalib_dirs.return_value = [
        DatalibDir(name="atlas", description=None),
        DatalibDir(name="census", description="# Census"),
    ]

    resp = client.get("/api/user/me/datalib")

    assert resp.status_code == 200
    assert resp.get_json() == {
        "dirs": [
            {"name": "atlas", "description": None},
            {"name": "census", "description": "# Census"},
        ]
    }
    manager.list_datalib_dirs.assert_called_once_with("u1")


def _submit(client):
    return client.post("/api/runs/submit", json={"runid": "r1"})


def test_submit_passes_datalib_dirs_to_the_job(client, manager):
    manager.get_metadata.return_value = {
        "datasets": [],
        "datalib_dirs": ["census"],
        "n_experiments": 3,
    }
    manager.missing_datalib_dirs.return_value = []

    _submit(client)

    manager.missing_datalib_dirs.assert_called_once_with("u1", ["census"])
    assert manager.run_job.call_args.kwargs["datalib_dirs"] == ["census"]


def test_submit_rejects_a_missing_datalib_dir(client, manager):
    manager.get_metadata.return_value = {"datalib_dirs": ["gone"], "n_experiments": 3}
    manager.missing_datalib_dirs.return_value = ["gone"]

    resp = _submit(client)

    assert resp.status_code == 400
    assert "gone" in resp.get_json()["error"]
    manager.run_job.assert_not_called()


def test_submit_rejects_an_invalid_datalib_dir(client, manager):
    manager.get_metadata.return_value = {"datalib_dirs": ["../x"], "n_experiments": 3}
    manager.missing_datalib_dirs.side_effect = ValueError("Invalid data library directory name")

    resp = _submit(client)

    assert resp.status_code == 400
    manager.run_job.assert_not_called()


def test_submit_requires_some_data(client, manager):
    manager.get_metadata.return_value = {"datasets": [], "n_experiments": 3}

    resp = _submit(client)

    assert resp.status_code == 400
    assert "at least one dataset" in resp.get_json()["error"]
    manager.run_job.assert_not_called()
