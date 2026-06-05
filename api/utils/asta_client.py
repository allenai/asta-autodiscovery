"""Client for calling the Asta API."""

import logging
import os

import requests

_log = logging.getLogger(__name__)

ASTA_BASE_URL = os.environ.get("ASTA_BASE_URL", "https://asta-rc.example.com")


def login_or_create_user(
    auth0_user_id: str,
    email: str,
    name: str,
    nickname: str,
) -> str:
    """Call Asta's /login endpoint and return the user UUID.

    Args:
        auth0_user_id: Auth0 subject identifier (sub claim)
        email: User's email address
        name: User's full name
        nickname: User's nickname

    Returns:
        User UUID string from Asta's UserModel

    Raises:
        requests.HTTPError: If the Asta login call fails
    """
    resp = requests.post(
        f"{ASTA_BASE_URL}/api/chat/login",
        json={
            "auth0_user_id": auth0_user_id,
            "email": email,
            "name": name,
            "nickname": nickname,
            "anonymous_user_id": None,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["user"]["uuid"]


def create_thread(auth_token: str, profile: str = "dv-a2a-only") -> str:
    """Create a new Asta thread and return the thread key.

    Args:
        auth_token: User's bearer token for Asta authentication
        profile: Handler profile to bind to the thread

    Returns:
        Thread key string (use as thread_id for subsequent calls)

    Raises:
        requests.HTTPError: If the thread creation call fails
    """
    resp = requests.put(
        f"{ASTA_BASE_URL}/api/chat/thread",
        params={"profile": profile, "channel_prefix": "datavoyager"},
        headers={"Authorization": f"Bearer {auth_token}"},
        timeout=30,
    )
    if not resp.ok:
        _log.error("Asta create_thread failed: status=%s body=%s", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()["thread"]["key"]


def send_dig_deeper_message(thread_id: str, formatted_query: str, auth_token: str) -> None:
    """Send the initial message to Asta DataVoyager via POST /api/chat/message.

    Args:
        thread_id: Asta thread key returned by create_thread
        formatted_query: User query with embedded <astaattachment> tag

    Raises:
        requests.HTTPError: If the message call fails
    """
    resp = requests.post(
        f"{ASTA_BASE_URL}/api/chat/message",
        json={
            "text": formatted_query,
            "thread_id": thread_id,
            "channel_prefix": "datavoyager",
        },
        headers={
            "Authorization": f"Bearer {auth_token}",
        },
        timeout=60,
    )
    resp.raise_for_status()
    _log.info("Message sent: thread_id=%s", thread_id)
