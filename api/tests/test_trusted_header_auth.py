"""Requests relayed by a trusted upstream: its secret and the headers naming the user."""

import pytest

# Flask is an api/ dependency, not a workspace one: `make test` layers in
# api/requirements.txt, but a bare `uv run pytest` skips this module.
flask = pytest.importorskip("flask")

from auth import auth_api  # noqa: E402
from autodiscovery_jobs import JobManager  # noqa: E402
from runs import runs_api  # noqa: E402
from user import user_api  # noqa: E402
from utils.auth import reset_auth_provider  # noqa: E402
from utils.auth.base import AuthConfigError, InvalidCredentialsError  # noqa: E402
from utils.auth.chain import ProviderChain  # noqa: E402
from utils.auth.factory import get_auth_provider  # noqa: E402
from utils.auth.providers.password_file import PasswordFileProvider  # noqa: E402
from utils.auth.providers.trusted_header import (  # noqa: E402
    TrustedHeaderProvider,
    parse_user_headers,
)

SECRET = "upstream-secret"
USER_HEADERS = "X-Forwarded-User,X-Forwarded-Service=service:"
USER = "idp|1234567890"


class _Request:
    def __init__(self, headers):
        self.headers = headers


def _relayed(**named) -> dict:
    headers = {"Authorization": f"Bearer {SECRET}"}
    for name, value in named.items():
        headers[f"X-Forwarded-{name.capitalize()}"] = value
    return headers


AS_USER = _relayed(user=USER)
AS_SERVICE = _relayed(service="ci-bot")


def _provider(spec=USER_HEADERS) -> TrustedHeaderProvider:
    return TrustedHeaderProvider(SECRET, parse_user_headers(spec))


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The runs, user and auth APIs behind AUTH_PROVIDER=trusted_header,password_file,
    on a local store under ``tmp_path``."""
    monkeypatch.setenv("AUTH_PROVIDER", "trusted_header,password_file")
    monkeypatch.setenv("AUTH_TRUSTED_HEADER_SECRET", SECRET)
    monkeypatch.setenv("AUTH_TRUSTED_HEADER_USER", USER_HEADERS)
    monkeypatch.setenv("AUTH_PASSWORD_DIR", str(tmp_path / "passwords"))
    monkeypatch.setenv("AUTH_SESSION_SECRET", "session-secret-" + "x" * 32)
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


def test_it_goes_ahead_of_the_interactive_provider(client):
    provider = get_auth_provider()
    assert isinstance(provider, ProviderChain)
    assert [type(p) for p in provider.providers] == [TrustedHeaderProvider, PasswordFileProvider]
    assert client.get("/api/auth/config").get_json()["provider"] == "password_file"


def test_it_needs_its_secret(client, monkeypatch):
    monkeypatch.delenv("AUTH_TRUSTED_HEADER_SECRET")
    reset_auth_provider()
    with pytest.raises(AuthConfigError, match="AUTH_TRUSTED_HEADER_SECRET"):
        get_auth_provider()
    response = client.post("/api/runs/create", headers=AS_USER)
    assert response.status_code == 500


def test_the_default_user_header(monkeypatch):
    monkeypatch.setenv("AUTH_TRUSTED_HEADER_SECRET", SECRET)
    monkeypatch.delenv("AUTH_TRUSTED_HEADER_USER", raising=False)
    user = TrustedHeaderProvider.from_env().authenticate(_Request(AS_USER))
    assert user.sub == USER


@pytest.mark.parametrize(
    ("spec", "reason"),
    [
        ("", "names no header"),
        ("X-User,x-user=p:", "twice"),
        ("X User", "not a header name"),
    ],
)
def test_bad_user_header_lists_are_config_errors(spec, reason):
    with pytest.raises(AuthConfigError, match=reason):
        parse_user_headers(spec)


# --- the provider ----------------------------------------------------------


@pytest.mark.parametrize(
    ("headers", "sub"),
    [(AS_USER, USER), (AS_SERVICE, "service:ci-bot")],
)
def test_the_named_user(headers, sub):
    user = _provider().authenticate(_Request(headers))
    assert (user.sub, user.permissions) == (sub, [])


@pytest.mark.parametrize(
    ("headers", "reason"),
    [
        (_relayed(), "names no user"),
        (_relayed(user=USER, service="ci-bot"), "more than one"),
        (_relayed(user="../other-user"), "can't store"),
        (_relayed(service="a/b"), "can't store"),
    ],
)
def test_bad_identities_are_refused(headers, reason):
    with pytest.raises(InvalidCredentialsError, match=reason):
        _provider().authenticate(_Request(headers))


@pytest.mark.parametrize(
    "authorization", [None, "Bearer not-the-secret", f"Basic {SECRET}", f"Bearer {SECRET}x"]
)
def test_it_recognizes_only_its_secret(authorization):
    headers = {"X-Forwarded-User": USER}
    if authorization:
        headers["Authorization"] = authorization
    provider = _provider()
    assert not provider.recognizes(_Request(headers))
    with pytest.raises(InvalidCredentialsError):
        provider.authenticate(_Request(headers))


# --- through the API -------------------------------------------------------


def test_relayed_users_runs_land_under_their_id_and_resolve_as_me(client):
    created = client.post("/api/runs/create", headers=AS_USER)
    assert created.status_code == 200
    runid = created.get_json()["runid"]
    # The default upload limit: relayed callers hold no permissions.
    assert created.get_json()["max_file_size"] is None
    assert JobManager().list_jobs(USER) == [runid]

    listed = client.get("/api/runs/me/list", headers=AS_USER)
    assert [r["runid"] for r in listed.get_json()["runs"]] == [runid]


def test_a_prefixed_caller_is_kept_apart(client):
    created = client.post("/api/runs/create", headers=AS_SERVICE)
    assert JobManager().list_jobs("service:ci-bot") == [created.get_json()["runid"]]


def test_user_headers_without_the_secret_are_refused(client):
    headers = {**AS_USER, "Authorization": "Bearer not-the-secret"}
    assert client.post("/api/runs/create", headers=headers).status_code == 401
    assert client.get("/api/runs/me/list", headers=headers).status_code == 401


def test_me_profile_is_the_named_user(client):
    response = client.get("/api/user/me", headers=AS_USER)
    assert response.status_code == 200
    assert response.get_json()["user"]["sub"] == USER


def test_another_users_runs_stay_private(client):
    client.post("/api/runs/create", headers=AS_SERVICE)
    response = client.get("/api/runs/service:ci-bot/list", headers=AS_USER)
    assert response.status_code == 403
