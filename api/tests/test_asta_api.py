"""The Asta handoff is self-contained and off unless its context service is configured."""

import gzip
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from urllib3.response import HTTPResponse

# Flask is an api/ dependency, not a workspace one: `make test` layers in
# api/requirements.txt, but a bare `uv run pytest` skips this module.
flask = pytest.importorskip("flask")

from asta import asta_api, context_client  # noqa: E402
from autodiscovery_jobs.storage.local import FilesystemStore  # noqa: E402
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
def import_dependencies(tmp_path):
    """Keep remote services and run storage out of integration route tests."""
    find_owned_artifact = context_client.find_owned_artifact
    get_download_url = context_client.get_download_url
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
            "artifact_id": "artifact-1",
            "path": "gs://example/owners/asta-user/context/input.csv",
        }
        profile = MagicMock()
        profile.json.return_value = {"email": "test@example.invalid", "name": "Test User"}
        download = MagicMock()
        download.headers = {"Content-Length": "12", "Content-Type": "text/csv"}
        download.raw = BytesIO(b"col1\nsample\n")
        response = MagicMock()
        response.__enter__.return_value = download
        http_get.side_effect = [profile, response]
        storage = FilesystemStore(tmp_path / "store")
        get_store.return_value = MagicMock(wraps=storage)
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
            "storage": storage,
            "find_owned_artifact": find_owned_artifact,
            "get_download_url": get_download_url,
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
    deps["store"].write_stream.assert_called_once()
    key, stream = deps["store"].write_stream.call_args.args
    assert key == asta_api.dataset_key("u1", "r1", filename or "input.csv")
    assert deps["storage"].read_bytes(key) == b"col1\nsample\n"
    assert stream.tell() == 12
    assert deps["store"].write_stream.call_args.kwargs == {"content_type": "text/csv"}
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


@pytest.mark.parametrize(
    "filename",
    ["../input.csv", "dir/input.csv", "dir\\input.csv", ".", "..", "nul\x00.csv", "line\n.csv"],
)
def test_import_rejects_unsafe_filenames(client, import_dependencies, filename):
    resp = client.post(
        IMPORT_ARTIFACT,
        json={"artifact_id": "artifact-1", "filename": filename},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 400
    import_dependencies["store"].write_stream.assert_not_called()


def test_import_preserves_size_limit(client, import_dependencies):
    deps = import_dependencies
    oversize = asta_api.UPLOAD_MAX_FILE_SIZE_BYTES + 1
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


@pytest.mark.parametrize("content_length", [None, "4", "invalid"])
@pytest.mark.parametrize("existing", [False, True])
def test_import_bounds_actual_bytes_and_preserves_dataset(
    client, import_dependencies, content_length, existing, tmp_path
):
    deps = import_dependencies
    limit = 64 * 1024
    key = asta_api.dataset_key("u1", "r1", "input.csv")
    if existing:
        deps["storage"].write_bytes(key, b"previous dataset")
    deps["download"].headers = {} if content_length is None else {"Content-Length": content_length}
    deps["download"].raw = BytesIO(b"x" * (limit + 1))

    with patch.object(asta_api, "UPLOAD_MAX_FILE_SIZE_BYTES", limit):
        resp = client.post(
            IMPORT_ARTIFACT,
            json={"artifact_id": "artifact-1"},
            headers={"Authorization": "Bearer test"},
        )

    assert resp.status_code == 413
    assert resp.json["error"] == "File too large."
    assert deps["download"].raw.tell() == limit + 1
    assert deps["storage"].exists(key) is existing
    if existing:
        assert deps["storage"].read_bytes(key) == b"previous dataset"
    assert not list((tmp_path / "store").rglob(".ad-staging.*"))
    deps["store"].delete.assert_not_called()


@pytest.mark.parametrize("size", [64, 65])
def test_import_bounds_decoded_gzip_bytes(client, import_dependencies, size):
    deps = import_dependencies
    compressed = gzip.compress(b"x" * size)
    deps["download"].headers = {"Content-Length": str(len(compressed))}
    deps["download"].raw = HTTPResponse(
        body=BytesIO(compressed),
        headers={"Content-Encoding": "gzip"},
        preload_content=False,
    )
    with patch.object(asta_api, "UPLOAD_MAX_FILE_SIZE_BYTES", 64):
        resp = client.post(
            IMPORT_ARTIFACT,
            json={"artifact_id": "artifact-1"},
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == (200 if size == 64 else 413)
    key = asta_api.dataset_key("u1", "r1", "input.csv")
    if size == 64:
        assert deps["storage"].read_bytes(key) == b"x" * size
    else:
        assert not deps["storage"].exists(key)


@pytest.mark.parametrize("existing", [False, True])
def test_import_failed_download_cleans_staging_without_deleting_dataset(
    client, import_dependencies, existing, tmp_path
):
    class InterruptedDownload(BytesIO):
        def read(self, size=-1):
            if self.tell():
                raise asta_api.requests.ConnectionError("interrupted download")
            return super().read(min(size, 64 * 1024))

    deps = import_dependencies
    key = asta_api.dataset_key("u1", "r1", "input.csv")
    if existing:
        deps["storage"].write_bytes(key, b"previous dataset")
    deps["download"].headers = {}
    deps["download"].raw = InterruptedDownload(b"x" * (128 * 1024))
    resp = client.post(
        IMPORT_ARTIFACT,
        json={"artifact_id": "artifact-1"},
        headers={"Authorization": "Bearer test"},
    )
    assert resp.status_code == 502
    assert deps["storage"].exists(key) is existing
    if existing:
        assert deps["storage"].read_bytes(key) == b"previous dataset"
    assert not list((tmp_path / "store").rglob(".ad-staging.*"))
    deps["store"].delete.assert_not_called()


def test_import_maps_gcs_wrapped_size_error_to_413(client, import_dependencies):
    from autodiscovery_jobs.storage.gcs import GcsStore

    deps = import_dependencies
    deps["download"].headers = {}
    store = GcsStore("example")

    def consume(stream, **kwargs):
        assert stream.tell() == 0
        while stream.read(4):
            pass

    with (
        patch.object(asta_api, "UPLOAD_MAX_FILE_SIZE_BYTES", 8),
        patch.object(asta_api, "get_store", return_value=store),
        patch.object(store, "_bucket") as bucket,
    ):
        bucket.return_value.blob.return_value.upload_from_file.side_effect = consume
        resp = client.post(
            IMPORT_ARTIFACT,
            json={"artifact_id": "artifact-1"},
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == 413
    bucket.return_value.blob.return_value.delete.assert_not_called()


def test_import_uses_owned_metadata_path_for_default_filename(client, import_dependencies):
    deps = import_dependencies
    deps["find_artifact"].side_effect = deps["find_owned_artifact"]
    artifacts = MagicMock()
    artifacts.json.return_value = {
        "artifacts": [
            {"metadata": None, "download_url": "https://data.example/untracked"},
            {
                "metadata": {
                    "artifact_id": "artifact-1",
                    "path": "gs://example/owners/asta-user/context/input.csv",
                    "name": "A display name without a file extension",
                },
                "download_url": "https://data.example/file",
            },
        ],
        "continuation": None,
    }
    url = MagicMock()
    url.json.return_value = {"download_url": "https://data.example/file", "metadata": None}
    deps["http_get"].side_effect = [deps["profile"], artifacts, url, deps["response"]]

    with (
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_URL", "https://context.example"),
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_API_KEY", "key"),
        patch.object(context_client, "get_download_url", side_effect=deps["get_download_url"]),
    ):
        resp = client.post(
            IMPORT_ARTIFACT,
            json={"artifact_id": "artifact-1"},
            headers={"Authorization": "Bearer test"},
        )
    assert resp.status_code == 200
    assert resp.json["filename"] == "input.csv"
