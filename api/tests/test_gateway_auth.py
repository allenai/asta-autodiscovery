"""Requests relayed by the API gateway: its service key, the identity headers, and `me`."""

from unittest.mock import patch

import pytest

# Flask is an api/ dependency, not a workspace one: `make test` layers in
# api/requirements.txt, but a bare `uv run pytest` skips this module.
flask = pytest.importorskip("flask")

from auth import auth_api  # noqa: E402
from autodiscovery_jobs import JobManager, get_user_profile  # noqa: E402
from runs import runs_api  # noqa: E402
from user import user_api  # noqa: E402
from utils.auth import reset_auth_provider  # noqa: E402
from utils.auth.base import (  # noqa: E402
    AuthConfigError,
    AuthProvider,
    InvalidCredentialsError,
    NoCredentialsError,
)
from utils.auth.chain import ProviderChain  # noqa: E402
from utils.auth.factory import get_auth_provider  # noqa: E402
from utils.auth.models import AuthenticatedUser  # noqa: E402
from utils.auth.providers.gateway import GatewayProvider  # noqa: E402
from utils.auth.providers.password_file import PasswordFileProvider  # noqa: E402

SERVICE_KEY = "gateway-service-key"
AUTH0_SUB = "google-oauth2|1234567890"
USER_UUID = "0b9d2c1e-6f1a-4f7e-9b51-1d3c5e7a9f00"
HEART = "gs://ai2-autodiscovery/public/CELLxGENE/heart.h5ad"


def _gateway(**identity) -> dict:
    headers = {"Authorization": f"Bearer {SERVICE_KEY}"}
    for name, value in identity.items():
        headers[f"x-asta-{name.replace('_', '-')}"] = value
    return headers


AS_USER = _gateway(auth0_sub=AUTH0_SUB, user_uuid=USER_UUID)
AS_STATIC_KEY = _gateway(static_key="ci-bot")


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The runs and user APIs behind AUTH_PROVIDER=gateway,password_file, on a
    local store under ``tmp_path``."""
    monkeypatch.setenv("AUTH_PROVIDER", "gateway,password_file")
    monkeypatch.setenv("AUTH_PASSWORD_DIR", str(tmp_path / "passwords"))
    monkeypatch.setenv("AUTH_SESSION_SECRET", "session-secret")
    monkeypatch.setenv("ASTA_GATEWAY_SERVICE_KEY", SERVICE_KEY)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "store"))
    monkeypatch.setenv("JOB_BACKEND", "docker")
    monkeypatch.setenv("AUTODISCOVERY_IMAGE", "autodiscovery:test")
    reset_auth_provider()
    app = flask.Flask(__name__)
    app.register_blueprint(runs_api.create(), url_prefix="/api/runs")
    app.register_blueprint(user_api.create(), url_prefix="/api/user")
    app.register_blueprint(auth_api.create(), url_prefix="/api/auth")
    yield app.test_client()
    reset_auth_provider()


# --- configuration ---------------------------------------------------------


def test_a_list_of_providers_is_a_chain_in_order(client):
    provider = get_auth_provider()
    assert isinstance(provider, ProviderChain)
    assert [type(p) for p in provider.providers] == [GatewayProvider, PasswordFileProvider]
    # The UI's login is the interactive provider's.
    assert provider.name == "password_file"


def test_the_ui_gets_the_interactive_providers_config(client):
    assert client.get("/api/auth/config").get_json()["provider"] == "password_file"


def test_one_provider_is_used_as_is(client, monkeypatch):
    monkeypatch.setenv("AUTH_PROVIDER", "password_file")
    reset_auth_provider()
    assert isinstance(get_auth_provider(), PasswordFileProvider)


@pytest.mark.parametrize(
    ("auth_provider", "reason"),
    [
        ("gateway,auth0,gateway", "twice"),
        ("gateway,kerberos", "Unknown AUTH_PROVIDER 'kerberos'"),
    ],
)
def test_bad_provider_lists_are_config_errors(client, monkeypatch, auth_provider, reason):
    monkeypatch.setenv("AUTH_PROVIDER", auth_provider)
    reset_auth_provider()
    with pytest.raises(AuthConfigError, match=reason):
        get_auth_provider()


def test_the_gateway_needs_its_key(client, monkeypatch):
    monkeypatch.delenv("ASTA_GATEWAY_SERVICE_KEY")
    reset_auth_provider()
    with pytest.raises(AuthConfigError, match="ASTA_GATEWAY_SERVICE_KEY"):
        get_auth_provider()
    response = client.post("/api/runs/create", headers=AS_USER)
    assert response.status_code == 500
    assert "ASTA_GATEWAY_SERVICE_KEY" in response.get_json()["error"]


# --- the chain -------------------------------------------------------------


class _Fake(AuthProvider):
    def __init__(self, name, *, claims, interactive=True):
        self.name, self._claims, self.interactive = name, claims, interactive

    @classmethod
    def from_env(cls):
        raise NotImplementedError

    def recognizes(self, request):
        return self._claims

    def authenticate(self, request):
        return AuthenticatedUser(sub=f"{self.name}-user")

    def user_profile(self, request, user):
        return {"from": self.name}


def test_the_first_provider_that_recognizes_the_request_authenticates_it():
    chain = ProviderChain(
        [
            _Fake("a", claims=False, interactive=False),
            _Fake("b", claims=True),
            _Fake("c", claims=True),
        ]
    )
    user = chain.authenticate(_Request({}))
    assert (user.sub, user.provider) == ("b-user", "b")
    assert chain.user_profile(_Request({}), user) == {"from": "b"}


def test_a_request_no_provider_recognizes_has_no_credentials():
    chain = ProviderChain([_Fake("a", claims=False), _Fake("b", claims=False)])
    with pytest.raises(NoCredentialsError):
        chain.authenticate(_Request({}))


# --- the gateway provider --------------------------------------------------


class _Request:
    def __init__(self, headers):
        self.headers = headers


@pytest.mark.parametrize(
    ("headers", "sub", "uuid"),
    [
        (AS_USER, AUTH0_SUB, USER_UUID),
        (_gateway(auth0_sub=AUTH0_SUB), AUTH0_SUB, None),
        (AS_STATIC_KEY, "static-key:ci-bot", None),
        # A static-key caller has no Asta user, whatever the headers say.
        (_gateway(static_key="ci-bot", user_uuid=USER_UUID), "static-key:ci-bot", None),
    ],
)
def test_gateway_identity(headers, sub, uuid):
    user = GatewayProvider(SERVICE_KEY).authenticate(_Request(headers))
    assert (user.sub, user.asta_user_uuid, user.permissions) == (sub, uuid, [])


@pytest.mark.parametrize(
    ("headers", "reason"),
    [
        (_gateway(), "names no user"),
        (_gateway(auth0_sub=AUTH0_SUB, static_key="ci-bot"), "both"),
        (_gateway(auth0_sub="../other-user"), "can't store"),
        (_gateway(static_key="a/b"), "can't store"),
    ],
)
def test_bad_gateway_identity_is_refused(headers, reason):
    with pytest.raises(InvalidCredentialsError, match=reason):
        GatewayProvider(SERVICE_KEY).authenticate(_Request(headers))


@pytest.mark.parametrize(
    "authorization", [None, "Bearer not-the-key", f"Basic {SERVICE_KEY}", f"Bearer {SERVICE_KEY}x"]
)
def test_the_gateway_recognizes_only_its_key(authorization):
    headers = {"x-asta-auth0-sub": AUTH0_SUB}
    if authorization:
        headers["Authorization"] = authorization
    gateway = GatewayProvider(SERVICE_KEY)
    assert not gateway.recognizes(_Request(headers))
    with pytest.raises(InvalidCredentialsError):
        gateway.authenticate(_Request(headers))


# --- through the API -------------------------------------------------------


def test_gateway_user_runs_land_under_their_auth0_sub_and_resolve_as_me(client):
    created = client.post("/api/runs/create", headers=AS_USER)
    assert created.status_code == 200
    runid = created.get_json()["runid"]
    # The default upload limit: gateway callers hold no permissions.
    assert created.get_json()["max_file_size"] is None

    assert JobManager().list_jobs(AUTH0_SUB) == [runid]

    listed = client.get("/api/runs/me/list", headers=AS_USER)
    assert listed.status_code == 200
    assert [r["runid"] for r in listed.get_json()["runs"]] == [runid]
    assert client.get(f"/api/runs/me/{runid}/status", headers=AS_USER).status_code == 200


def test_the_asta_user_uuid_is_recorded(client):
    client.post("/api/runs/create", headers=AS_USER)
    assert get_user_profile(AUTH0_SUB).asta_user_uuid == USER_UUID


def test_static_key_callers_are_a_service_account(client):
    created = client.post("/api/runs/create", headers=AS_STATIC_KEY)
    assert created.status_code == 200
    assert JobManager().list_jobs("static-key:ci-bot") == [created.get_json()["runid"]]
    assert get_user_profile("static-key:ci-bot") is None


def test_identity_headers_without_the_service_key_are_refused(client):
    headers = {**AS_USER, "Authorization": "Bearer not-the-key"}
    assert client.post("/api/runs/create", headers=headers).status_code == 401
    assert client.get("/api/runs/me/list", headers=headers).status_code == 401


def test_me_profile_is_the_named_identity(client):
    response = client.get("/api/user/me", headers=AS_USER)
    assert response.status_code == 200
    user = response.get_json()["user"]
    assert (user["sub"], user["asta_user_uuid"]) == (AUTH0_SUB, USER_UUID)


def test_another_users_runs_stay_private(client):
    client.post("/api/runs/create", headers=AS_STATIC_KEY)
    response = client.get("/api/runs/static-key:ci-bot/list", headers=AS_USER)
    assert response.status_code == 403


# --- preloaded datasets ----------------------------------------------------


def _run_with_dataset(client, url) -> str:
    runid = client.post("/api/runs/create", headers=AS_USER).get_json()["runid"]
    # No experiment count: a submit that gets past the dataset check stops at
    # validation with a 400, before any job is launched.
    JobManager().upload_metadata(
        AUTH0_SUB, runid, {"name": "Run", "datasets": [{"name": "data.h5ad", "url": url}]}
    )
    return runid


def test_a_preloaded_dataset_is_copied_without_any_enrollment(client):
    runid = _run_with_dataset(client, HEART)
    with patch.object(runs_api, "sync_preloaded_dataset") as sync:
        response = client.post("/api/runs/submit", headers=AS_USER, json={"runid": runid})
    sync.assert_called_once()
    assert sync.call_args.kwargs["source_gs_url"] == HEART
    assert response.status_code == 400
    assert "Number of Experiments" in response.get_json()["error"]


@pytest.mark.parametrize(
    "url",
    [
        "gs://ai2-autodiscovery/private/secrets.csv",
        "gs://ai2-autodiscovery/public/CELLxGENE/heart.h5ad.bak",
        "gs://another-bucket/data.h5ad",
    ],
)
def test_any_other_gs_url_is_refused(client, url):
    runid = _run_with_dataset(client, url)
    with patch.object(runs_api, "sync_preloaded_dataset") as sync:
        response = client.post("/api/runs/submit", headers=AS_USER, json={"runid": runid})
    sync.assert_not_called()
    assert response.status_code == 403
    assert "not one of the preloaded datasets" in response.get_json()["error"]
