"""Auth0 Management API client for user lookups.

This module provides functions to query Auth0 for user information,
specifically to retrieve user email addresses by user ID.

Required environment variables:
    AUTH0_MGMT_CLIENT_ID: Management API client ID
    AUTH0_MGMT_CLIENT_SECRET: Management API client secret

The client credentials must have the `read:users` scope.
"""

import json
import os
from functools import lru_cache
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


AUTH0_MGMT_DOMAIN = "YOUR_TENANT.us.auth0.com"


class Auth0Error(Exception):
    """Raised when Auth0 API calls fail."""

    pass


@lru_cache(maxsize=1)
def _get_management_token() -> str:
    """Get an Auth0 Management API access token.

    Uses client credentials grant to obtain a token.
    Token is cached for the lifetime of the process.
    """
    client_id = os.environ["AUTH0_MGMT_CLIENT_ID"]
    client_secret = os.environ["AUTH0_MGMT_CLIENT_SECRET"]

    token_url = f"https://{AUTH0_MGMT_DOMAIN}/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
        "audience": f"https://{AUTH0_MGMT_DOMAIN}/api/v2/",
    }

    try:
        data = urlencode(payload).encode("utf-8")
        req = Request(token_url, data=data, method="POST")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["access_token"]
    except HTTPError as e:
        # Read response body for more details
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            pass
        raise Auth0Error(
            f"Failed to get Auth0 management token: {e.code} {e.reason} - {body}"
        )
    except Exception as e:
        raise Auth0Error(f"Failed to get Auth0 management token: {e}")


def get_user(userid: str) -> dict[str, Any]:
    """Get user information from Auth0 by user ID."""
    from urllib.parse import quote

    token = _get_management_token()
    encoded_userid = quote(userid, safe="")
    user_url = f"https://{AUTH0_MGMT_DOMAIN}/api/v2/users/{encoded_userid}"

    try:
        req = Request(user_url, method="GET")
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Content-Type", "application/json")

        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        raise Auth0Error(f"Failed to get user {userid}: {e}")
