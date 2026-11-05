"""Several auth providers in one deployment, and `me` as the path user id."""

import pytest

# Flask is an api/ dependency, not a workspace one: `make test` layers in
# api/requirements.txt, but a bare `uv run pytest` skips this module.
flask = pytest.importorskip("flask")

from auth import auth_api  # noqa: E402
from autodiscovery_jobs import JobManager  # noqa: E402
from runs import runs_api  # noqa: E402
from user import user_api  # noqa: E402
from utils.auth import reset_auth_provider  # noqa: E402
from utils.auth.base import (  # noqa: E402
    AuthConfigError,
    AuthProvider,
    NoCredentialsError,
)
from utils.auth.chain import ProviderChain  # noqa: E402
from utils.auth.factory import get_auth_provider  # noqa: E402
from utils.auth.models import AuthenticatedUser  # noqa: E402
from utils.auth.password_store import PasswordStore  # noqa: E402
from utils.auth.providers.password_file import PasswordFileProvider  # noqa: E402

# --- the chain -------------------------------------------------------------


class _Request:
    def __init__(self, headers):
        self.headers = headers


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


class _TakesEverything(AuthProvider):
    name = "everything"

    @classmethod
    def from_env(cls):
        raise NotImplementedError

    def authenticate(self, request):
        return AuthenticatedUser(sub="everyone")


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


def test_the_login_is_the_first_interactive_providers():
    chain = ProviderChain([_Fake("service", claims=False, interactive=False), _TakesEverything()])
    assert chain.name == "everything"
    assert chain.public_config() == {"provider": "everything"}


def test_only_the_last_provider_may_take_every_request():
    with pytest.raises(AuthConfigError, match="must come last"):
        ProviderChain([_TakesEverything(), _Fake("b", claims=True)])


@pytest.mark.parametrize(
    ("auth_provider", "reason"),
    [
        ("auth0,password_file,auth0", "twice"),
        ("password_file,kerberos", "Unknown AUTH_PROVIDER 'kerberos'"),
        ("password_file,none", "must come last"),
    ],
)
def test_bad_provider_lists_are_config_errors(client, monkeypatch, auth_provider, reason):
    monkeypatch.setenv("AUTH_PROVIDER", auth_provider)
    reset_auth_provider()
    with pytest.raises(AuthConfigError, match=reason):
        get_auth_provider()


def test_one_provider_is_used_as_is(client):
    assert isinstance(get_auth_provider(), PasswordFileProvider)


# --- `me` --------------------------------------------------------------------

USER_ID = "file|alice"


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The runs, user and auth APIs behind AUTH_PROVIDER=password_file, on a
    local store under ``tmp_path``."""
    passwords = tmp_path / "passwords"
    passwords.mkdir()
    PasswordStore.in_dir(passwords).add_user("alice", "alice-password")
    PasswordStore.in_dir(passwords).add_user("bob", "bob-password")
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
    app.register_blueprint(user_api.create(), url_prefix="/api/user")
    app.register_blueprint(auth_api.create(), url_prefix="/api/auth")
    yield app.test_client()
    reset_auth_provider()


def _sign_in(client, username) -> dict:
    response = client.post(
        "/api/auth/login", json={"username": username, "password": f"{username}-password"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_me_is_the_caller(client):
    alice = _sign_in(client, "alice")
    runid = client.post("/api/runs/create", headers=alice).get_json()["runid"]
    assert JobManager().list_jobs(USER_ID) == [runid]

    listed = client.get("/api/runs/me/list", headers=alice)
    assert listed.status_code == 200
    assert [r["runid"] for r in listed.get_json()["runs"]] == [runid]
    assert client.get(f"/api/runs/me/{runid}/status", headers=alice).status_code == 200


def test_me_is_each_callers_own(client):
    client.post("/api/runs/create", headers=_sign_in(client, "alice"))
    listed = client.get("/api/runs/me/list", headers=_sign_in(client, "bob"))
    assert listed.status_code == 200
    assert listed.get_json()["runs"] == []


def test_me_needs_a_signed_in_caller(client):
    assert client.get("/api/runs/me/list").status_code == 401


def test_another_users_runs_stay_private(client):
    response = client.get(f"/api/runs/{USER_ID}/list", headers=_sign_in(client, "bob"))
    assert response.status_code == 403
