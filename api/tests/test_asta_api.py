"""The Asta handoff is self-contained and off unless its context service is configured."""

from unittest.mock import MagicMock, patch

import pytest

# Flask is an api/ dependency, not a workspace one: `make test` layers in
# api/requirements.txt, but a bare `uv run pytest` skips this module.
flask = pytest.importorskip("flask")

from asta import asta_api, context_client  # noqa: E402
from utils.auth.models import AuthenticatedUser  # noqa: E402

DIG_DEEPER = "/api/runs/u1/r1/experiments/node_0_0/dig-deeper"


@pytest.fixture
def client():
    provider = MagicMock()
    provider.authenticate.return_value = AuthenticatedUser(sub="u1", permissions=[])
    app = flask.Flask(__name__)
    app.register_blueprint(asta_api.create(), url_prefix="/api/runs")
    with patch("utils.auth.decorators.get_auth_provider", return_value=provider):
        yield app.test_client()


def test_dig_deeper_unconfigured_returns_503(client):
    with (
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_URL", ""),
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_API_KEY", ""),
        patch.object(asta_api, "JobManager") as job_manager,
    ):
        resp = client.post(DIG_DEEPER, json={"query": "why?"})

    assert resp.status_code == 503
    job_manager.assert_not_called()


def test_dig_deeper_rejects_other_users_run(client):
    with (
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_URL", "https://context.example"),
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_API_KEY", "key"),
    ):
        resp = client.post(
            "/api/runs/someone-else/r1/experiments/node_0_0/dig-deeper", json={"query": "why?"}
        )

    assert resp.status_code == 403


IMPORT_ARTIFACT = "/api/runs/r1/import-context-artifact"


@pytest.fixture
def import_dependencies():
    """Keep remote services and run storage out of integration route tests."""
    with (
        patch.object(asta_api, "is_enabled", return_value=True),
        patch.object(asta_api, "JobConfig"),
        patch.object(asta_api, "JobManager") as manager,
        patch.object(asta_api, "get_store") as get_store,
        patch.object(asta_api.client, "login_or_create_user", return_value="asta-user") as login,
        patch.object(context_client, "find_owned_artifact") as find_artifact,
        patch.object(context_client, "get_download_url", return_value="https://data.example/file"),
        patch.object(asta_api.requests, "get") as http_get,
        patch.dict("os.environ", {"AUTH0_DOMAIN": "auth.example"}),
    ):
        find_artifact.return_value = {
            "filename": "input.csv",
            "file_size_bytes": 12,
            "content_type": "text/csv",
        }
        profile = MagicMock()
        profile.json.return_value = {"email": "test@example.invalid", "name": "Test User"}
        download = MagicMock()
        download.headers = {"Content-Length": "12"}
        response = MagicMock()
        response.__enter__.return_value = download
        http_get.side_effect = [profile, response]
        get_store.return_value.uri.return_value = "memory://runs/r1/data/input.csv"
        yield {
            "manager": manager.return_value,
            "store": get_store.return_value,
            "login": login,
            "find_artifact": find_artifact,
            "http_get": http_get,
            "profile": profile,
            "response": response,
            "download": download,
        }


def test_import_unconfigured_returns_404(client):
    with (
        patch.object(asta_api, "is_enabled", return_value=False),
        patch.object(asta_api, "JobManager") as manager,
    ):
        resp = client.post(IMPORT_ARTIFACT, json={"artifact_id": "artifact-1"})
    assert resp.status_code == 404
    manager.assert_not_called()


@pytest.mark.parametrize("filename", [None, "renamed.csv"])
def test_import_streams_owned_artifact_at_existing_url(client, import_dependencies, filename):
    deps = import_dependencies
    body = {"artifact_id": "artifact-1"}
    if filename:
        body["filename"] = filename
    resp = client.post(IMPORT_ARTIFACT, json=body, headers={"Authorization": "Bearer test"})
    assert resp.status_code == 200
    assert resp.json["filename"] == (filename or "input.csv")
    assert resp.json["message"] == "Dataset imported from Asta"
    deps["manager"].job_exists.assert_called_once_with("u1", "r1")
    deps["find_artifact"].assert_called_once_with("asta-user", "artifact-1")
    deps["login"].assert_called_once_with(
        auth0_user_id="u1",
        email="test@example.invalid",
        name="Test User",
        nickname="test@example.invalid",
    )
    deps["store"].write_stream.assert_called_once_with(
        asta_api.dataset_key("u1", "r1", filename or "input.csv"),
        deps["download"].raw,
        content_type="text/csv",
    )
    assert deps["download"].raw.decode_content is True


def test_import_missing_run_does_not_contact_asta(client, import_dependencies):
    deps = import_dependencies
    deps["manager"].job_exists.return_value = False
    resp = client.post(IMPORT_ARTIFACT, json={"artifact_id": "artifact-1"})
    assert resp.status_code == 404
    deps["http_get"].assert_not_called()


def test_import_unowned_artifact_is_not_downloaded(client, import_dependencies):
    deps = import_dependencies
    deps["find_artifact"].return_value = None
    resp = client.post(
        IMPORT_ARTIFACT,
        json={"artifact_id": "artifact-1"},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 404
    assert deps["http_get"].call_count == 1
    deps["store"].write_stream.assert_not_called()


@pytest.mark.parametrize("filename", ["../input.csv", "dir/input.csv", "dir\\input.csv", ".", ".."])
def test_import_rejects_unsafe_filenames(client, import_dependencies, filename):
    resp = client.post(
        IMPORT_ARTIFACT,
        json={"artifact_id": "artifact-1", "filename": filename},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 400
    import_dependencies["store"].write_stream.assert_not_called()


@pytest.mark.parametrize("size_source", ["metadata", "download"])
def test_import_preserves_size_limit(client, import_dependencies, size_source):
    deps = import_dependencies
    oversize = asta_api.UPLOAD_MAX_FILE_SIZE_BYTES + 1
    if size_source == "metadata":
        deps["find_artifact"].return_value["file_size_bytes"] = oversize
    else:
        deps["download"].headers["Content-Length"] = str(oversize)
    resp = client.post(
        IMPORT_ARTIFACT,
        json={"artifact_id": "artifact-1"},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 413
    deps["store"].write_stream.assert_not_called()


def test_import_missing_authorization_header_fails_cleanly(client, import_dependencies):
    resp = client.post(IMPORT_ARTIFACT, json={"artifact_id": "artifact-1"})
    assert resp.status_code == 502
    assert resp.json["error"] == "Failed to fetch user profile from Auth0"
    import_dependencies["login"].assert_not_called()


def test_import_retries_profile_fetch(client, import_dependencies):
    deps = import_dependencies
    deps["http_get"].side_effect = [
        asta_api.requests.ConnectionError("temporary failure"),
        deps["profile"],
        deps["response"],
    ]
    resp = client.post(
        IMPORT_ARTIFACT,
        json={"artifact_id": "artifact-1"},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 200
    assert deps["http_get"].call_count == 3


def test_dig_deeper_uses_shared_identity_for_handoff(client, import_dependencies):
    from types import SimpleNamespace

    deps = import_dependencies
    deps["manager"].get_metadata.return_value = {"description": "A synthetic run", "datasets": []}
    node = SimpleNamespace(
        code="print(1)",
        hypothesis="Example",
        experiment_plan={},
        analysis="Example",
        code_output="1",
        level=0,
        index=0,
        creation_idx=1,
    )
    with (
        patch.object(asta_api.ExperimentTree, "load_node", return_value=node),
        patch.object(asta_api, "read_rich_outputs", return_value=[]),
        patch.object(asta_api.client, "create_thread", return_value="thread-1") as thread,
        patch.object(
            context_client, "upload_json_artifact", return_value="gs://example/manifest"
        ) as manifest,
        patch.object(asta_api.workspace, "copy_dataset_to_asta_workspace", return_value=[]),
        patch.object(asta_api.client, "send_dig_deeper_message") as send,
    ):
        resp = client.post(
            DIG_DEEPER,
            json={"query": "why?"},
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == 200
    deps["login"].assert_called_once()
    assert manifest.call_args.kwargs["owner_id"] == "asta-user"
    assert thread.call_args.args == ("test",)
    assert send.call_args.args[0] == "thread-1"
    assert send.call_args.args[2] == "test"


def test_import_honors_higher_upload_permission(client, import_dependencies):
    deps = import_dependencies
    size = asta_api.UPLOAD_MAX_FILE_SIZE_BYTES + 1
    deps["find_artifact"].return_value["file_size_bytes"] = size
    deps["download"].headers["Content-Length"] = str(size)
    provider = MagicMock()
    provider.authenticate.return_value = AuthenticatedUser(
        sub="u1", permissions=[asta_api.PermissionType.HIGHER_UPLOAD_LIMIT.value]
    )
    with patch("utils.auth.decorators.get_auth_provider", return_value=provider):
        resp = client.post(
            IMPORT_ARTIFACT,
            json={"artifact_id": "artifact-1"},
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == 200
    deps["store"].write_stream.assert_called_once()


@pytest.mark.parametrize("failure", ["profile", "login"])
def test_import_identity_failure_stops_artifact_lookup(client, import_dependencies, failure):
    deps = import_dependencies
    if failure == "profile":
        deps["http_get"].side_effect = asta_api.requests.ConnectionError("unavailable")
    else:
        deps["login"].side_effect = RuntimeError("unavailable")
    resp = client.post(
        IMPORT_ARTIFACT,
        json={"artifact_id": "artifact-1"},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 502
    deps["find_artifact"].assert_not_called()
    deps["store"].write_stream.assert_not_called()
