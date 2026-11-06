"""AUTH_PROVIDER=trusted_header,password_file: the chain, the trusted upstream, and `me`."""

import pytest

# Flask is an api/ dependency, not a workspace one: `make test` layers in
# api/requirements.txt, but a bare `uv run pytest` skips this module.
flask = pytest.importorskip("flask")

from auth import auth_api  # noqa: E402
from autodiscovery_jobs import JobManager  # noqa: E402
from runs import runs_api  # noqa: E402
from user import user_api  # noqa: E402
from utils.auth import reset_auth_provider  # noqa: E402
from utils.auth.base import AuthConfigError  # noqa: E402
from utils.auth.factory import get_auth_provider  # noqa: E402

SECRET = "upstream-secret"
USER = "idp|1234567890"


def _relayed(**named) -> dict:
    headers = {"Authorization": f"Bearer {SECRET}"}
    headers.update({f"X-Forwarded-{k.capitalize()}": v for k, v in named.items()})
    return headers


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTH_PROVIDER", "trusted_header,password_file")
    monkeypatch.setenv("AUTH_TRUSTED_HEADER_SECRET", SECRET)
    monkeypatch.setenv("AUTH_TRUSTED_HEADER_USER", "X-Forwarded-User,X-Forwarded-Service=service:")
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


@pytest.mark.parametrize(
    ("env", "reason"),
    [
        ({"AUTH_PROVIDER": "password_file,trusted_header,password_file"}, "twice"),
        ({"AUTH_PROVIDER": "trusted_header,kerberos"}, "Unknown AUTH_PROVIDER 'kerberos'"),
        ({"AUTH_PROVIDER": "password_file,trusted_header"}, "must come last"),
        ({"AUTH_TRUSTED_HEADER_SECRET": ""}, "AUTH_TRUSTED_HEADER_SECRET"),
        ({"AUTH_TRUSTED_HEADER_USER": "X User"}, "not a header name"),
    ],
)
def test_config_errors(client, monkeypatch, env, reason):
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    reset_auth_provider()
    with pytest.raises(AuthConfigError, match=reason):
        get_auth_provider()


def test_the_ui_login_is_the_interactive_providers(client):
    assert client.get("/api/auth/config").get_json()["provider"] == "password_file"


def test_a_relayed_user_owns_their_runs_as_me(client):
    created = client.post("/api/runs/create", headers=_relayed(user=USER))
    assert created.status_code == 200
    runid = created.get_json()["runid"]
    assert JobManager().list_jobs(USER) == [runid]
    # Relayed callers hold no permissions, so the default upload limit.
    assert created.get_json()["max_file_size"] is None

    listed = client.get("/api/runs/me/list", headers=_relayed(user=USER))
    assert [r["runid"] for r in listed.get_json()["runs"]] == [runid]
    assert client.get("/api/user/me", headers=_relayed(user=USER)).get_json()["user"]["sub"] == USER


def test_a_prefix_keeps_callers_apart(client):
    runid = client.post("/api/runs/create", headers=_relayed(service="ci-bot")).get_json()["runid"]
    assert JobManager().list_jobs("service:ci-bot") == [runid]
    other = client.get("/api/runs/service:ci-bot/list", headers=_relayed(user=USER))
    assert other.status_code == 403


@pytest.mark.parametrize(
    "headers",
    [
        {"X-Forwarded-User": USER},  # no secret: falls through to password_file
        {**_relayed(user=USER), "Authorization": "Bearer not-the-secret"},
        {**_relayed(user=USER), "Authorization": f"Basic {SECRET}"},
        _relayed(),  # names no user
        _relayed(user=USER, service="ci-bot"),  # names two
        _relayed(user="../other-user"),  # not one path segment
    ],
)
def test_refused(client, headers):
    assert client.post("/api/runs/create", headers=headers).status_code == 401


def test_me_needs_a_caller(client):
    assert client.get("/api/runs/me/list").status_code == 401
