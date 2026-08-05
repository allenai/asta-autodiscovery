"""Tests for local AI provider credential persistence."""

from __future__ import annotations

import os

import keyring.backend
import keyring.errors
from utils import provider_credentials


class MemoryKeyring(keyring.backend.KeyringBackend):
    """Minimal in-memory backend that never touches the real user Keychain."""

    priority = 1

    def __init__(self) -> None:
        self.values: dict[tuple[str, str], str] = {}

    def get_password(self, servicename: str, username: str) -> str | None:
        return self.values.get((servicename, username))

    def set_password(self, servicename: str, username: str, password: str) -> None:
        self.values[(servicename, username)] = password

    def delete_password(self, servicename: str, username: str) -> None:
        try:
            del self.values[(servicename, username)]
        except KeyError as exc:
            raise keyring.errors.PasswordDeleteError from exc


def test_save_load_and_delete_provider_credentials(monkeypatch) -> None:
    """Persist secrets without returning them and restore them for worker inheritance."""
    backend = MemoryKeyring()
    monkeypatch.setattr(provider_credentials.keyring, "get_keyring", lambda: backend)
    monkeypatch.setattr(provider_credentials.keyring, "get_password", backend.get_password)
    monkeypatch.setattr(provider_credentials.keyring, "set_password", backend.set_password)
    monkeypatch.setattr(provider_credentials.keyring, "delete_password", backend.delete_password)
    for env_name in (
        "OPENAI_API_KEY",
        "VERTEX_ACCESS_TOKEN",
        "VERTEX_PROJECT_ID",
        "VERTEX_LOCATION",
    ):
        monkeypatch.delenv(env_name, raising=False)

    provider_credentials.save_provider_configuration("openai", {"api_key": "sk-secret"})
    provider_credentials.save_provider_configuration(
        "vertex",
        {"access_token": "vertex-secret", "project_id": "study-project", "location": "us-west1"},
    )
    status = provider_credentials.provider_configuration()

    assert status == {
        "openai": {"configured": True},
        "vertex": {"configured": True, "project_id": "study-project", "location": "us-west1"},
    }
    assert "secret" not in repr(status)
    monkeypatch.delenv("OPENAI_API_KEY")
    provider_credentials.load_provider_credentials()
    assert os.environ["OPENAI_API_KEY"] == "sk-secret"

    provider_credentials.delete_provider_configuration("openai")
    assert provider_credentials.provider_configuration()["openai"] == {"configured": False}


def test_rejects_missing_secret() -> None:
    """Require the provider's secret credential before persisting configuration."""
    try:
        provider_credentials.save_provider_configuration("openai", {"api_key": ""})
    except ValueError as exc:
        assert "Api Key is required" in str(exc)
    else:
        raise AssertionError("Expected an empty OpenAI key to be rejected")
