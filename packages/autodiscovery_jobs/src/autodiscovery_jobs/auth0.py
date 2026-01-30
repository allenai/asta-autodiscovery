"""Auth0 Management API client for user lookups.

This module provides functions to query Auth0 for user information,
specifically to retrieve user email addresses by user ID.

Required environment variables:
    AUTH0_DOMAIN: Auth0 tenant domain (e.g., "auth.example.com")
    AUTH0_MGMT_CLIENT_ID: Management API client ID
    AUTH0_MGMT_CLIENT_SECRET: Management API client secret

The client credentials must have the `read:users` scope.
"""

import os
from functools import lru_cache
from typing import Any
from urllib.request import Request, urlopen
from urllib.parse import urlencode
import json


class Auth0Error(Exception):
    """Raised when Auth0 API calls fail."""

    pass


def _get_env_or_raise(name: str) -> str:
    """Get environment variable or raise error."""
    value = os.environ.get(name)
    if not value:
        raise Auth0Error(f"Missing required environment variable: {name}")
    return value


@lru_cache(maxsize=1)
def _get_management_token() -> str:
    """Get an Auth0 Management API access token.

    Uses client credentials grant to obtain a token.
    Token is cached for the lifetime of the process.

    Returns:
        Access token string

    Raises:
        Auth0Error: If token acquisition fails
    """
    domain = _get_env_or_raise("AUTH0_DOMAIN")
    client_id = _get_env_or_raise("AUTH0_MGMT_CLIENT_ID")
    client_secret = _get_env_or_raise("AUTH0_MGMT_CLIENT_SECRET")

    token_url = f"https://{domain}/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": f"https://{domain}/api/v2/",
    }

    try:
        data = urlencode(payload).encode("utf-8")
        req = Request(token_url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["access_token"]
    except Exception as e:
        raise Auth0Error(f"Failed to get Auth0 management token: {e}")


def get_user(userid: str) -> dict[str, Any]:
    """Get user information from Auth0 by user ID.

    Args:
        userid: Auth0 user ID (e.g., "google-oauth2|123456789")

    Returns:
        User dictionary with fields like email, name, etc.

    Raises:
        Auth0Error: If user lookup fails
    """
    domain = _get_env_or_raise("AUTH0_DOMAIN")
    token = _get_management_token()

    # URL encode the user ID (contains special characters like |)
    from urllib.parse import quote
    encoded_userid = quote(userid, safe="")

    user_url = f"https://{domain}/api/v2/users/{encoded_userid}"

    try:
        req = Request(user_url, method="GET")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")

        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        raise Auth0Error(f"Failed to get user {userid}: {e}")


def get_user_email(userid: str) -> str | None:
    """Get user's email address from Auth0.

    Args:
        userid: Auth0 user ID (e.g., "google-oauth2|123456789")

    Returns:
        User's email address, or None if not found

    Raises:
        Auth0Error: If user lookup fails
    """
    user = get_user(userid)
    return user.get("email")
