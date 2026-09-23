"""Tests for the Auth0 Management API client."""

from urllib.error import HTTPError

import pytest
from autodiscovery_jobs import auth0


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AUTH0_MGMT_DOMAIN", "tenant.example.com")
    monkeypatch.setattr(auth0, "_get_management_token", lambda: "token")


def _raise_http(code):
    def _urlopen(req, timeout):
        raise HTTPError(req.full_url, code, "error", {}, None)

    return _urlopen


def test_get_user_missing_record_raises_not_found(monkeypatch):
    monkeypatch.setattr(auth0, "urlopen", _raise_http(404))

    with pytest.raises(auth0.Auth0UserNotFoundError):
        auth0.get_user("auth0|gone")


def test_get_user_other_http_error_is_not_not_found(monkeypatch):
    monkeypatch.setattr(auth0, "urlopen", _raise_http(500))

    with pytest.raises(auth0.Auth0Error) as exc_info:
        auth0.get_user("auth0|someone")
    assert not isinstance(exc_info.value, auth0.Auth0UserNotFoundError)
