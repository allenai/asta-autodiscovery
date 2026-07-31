"""Keychain-backed credentials for local AI providers."""

from __future__ import annotations

import contextlib
import os
from typing import Any

import keyring

_SERVICE = "org.allenai.autodiscovery.providers"
_FIELDS = {
    "openai": {"api_key": "OPENAI_API_KEY"},
    "vertex": {
        "access_token": "VERTEX_ACCESS_TOKEN",
        "project_id": "VERTEX_PROJECT_ID",
        "location": "VERTEX_LOCATION",
    },
}
_SECRET_FIELDS = {"openai": {"api_key"}, "vertex": {"access_token"}}


def _account(provider: str, field: str) -> str:
    return f"{provider}.{field}"


def load_provider_credentials() -> None:
    """Load saved provider values into the API environment for worker inheritance."""
    for provider, fields in _FIELDS.items():
        for field, env_name in fields.items():
            if os.environ.get(env_name):
                continue
            value = keyring.get_password(_SERVICE, _account(provider, field))
            if value:
                os.environ[env_name] = value


def provider_configuration() -> dict[str, dict[str, Any]]:
    """Return non-secret provider configuration state."""
    result: dict[str, dict[str, Any]] = {}
    for provider, fields in _FIELDS.items():
        values = {
            field: os.environ.get(env_name)
            or keyring.get_password(_SERVICE, _account(provider, field))
            for field, env_name in fields.items()
        }
        public_values = {
            field: value
            for field, value in values.items()
            if field not in _SECRET_FIELDS[provider] and value
        }
        required = _SECRET_FIELDS[provider]
        result[provider] = {
            "configured": all(bool(values.get(field)) for field in required),
            **public_values,
        }
    return result


def save_provider_configuration(provider: str, values: dict[str, Any]) -> None:
    """Persist allowed provider fields and update the live API environment."""
    if provider not in _FIELDS:
        raise ValueError("Unsupported provider")
    allowed_fields = _FIELDS[provider]
    required = _SECRET_FIELDS[provider]
    for field in required:
        if not str(values.get(field) or "").strip():
            raise ValueError(f"{field.replace('_', ' ').title()} is required")
    for field, env_name in allowed_fields.items():
        value = str(values.get(field) or "").strip()
        if not value:
            if field == "location" and provider == "vertex":
                value = "global"
            else:
                continue
        keyring.set_password(_SERVICE, _account(provider, field), value)
        os.environ[env_name] = value


def delete_provider_configuration(provider: str) -> None:
    """Remove all saved values for a provider from Keychain and the live environment."""
    if provider not in _FIELDS:
        raise ValueError("Unsupported provider")
    for field, env_name in _FIELDS[provider].items():
        with contextlib.suppress(keyring.errors.PasswordDeleteError):
            keyring.delete_password(_SERVICE, _account(provider, field))
        os.environ.pop(env_name, None)
