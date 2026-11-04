"""Requests relayed by the Asta API gateway.

The gateway authenticates its own callers, then calls this API with its
service key as the bearer and names the caller in headers:

    x-asta-auth0-sub    the user's Auth0 subject
    x-asta-user-uuid    the same user's Asta user UUID, when the gateway knows it
    x-asta-static-key   the name of the static key a service caller used

The gateway strips any copy of these headers its caller sends, so they are
trusted here only on a request that carries the service key. A user is keyed
on their Auth0 subject, the same `sub` the Auth0 provider gives them, so their
runs are the same whether they come through the UI or the gateway. A static-key
caller is the service account `static-key:<name>`.

Gateway callers hold no permissions: preloaded datasets are open to every
user, and the default upload limit applies.

It recognizes only requests bearing its key, so it is listed before a provider
that takes any bearer: AUTH_PROVIDER=gateway,auth0.
"""

from __future__ import annotations

import hmac
import os
import re

from ..base import AuthConfigError, AuthProvider, InvalidCredentialsError
from ..models import AuthenticatedUser

AUTH0_SUB_HEADER = "x-asta-auth0-sub"
USER_UUID_HEADER = "x-asta-user-uuid"
STATIC_KEY_HEADER = "x-asta-static-key"

# A user id becomes a storage prefix (users/{sub}/), so it must be one path
# segment: Auth0 subjects look like "google-oauth2|123" or "auth0|abc".
_SAFE_ID = re.compile(r"^[A-Za-z0-9|_.@:+-]+$")


class GatewayProvider(AuthProvider):
    name = "gateway"
    interactive = False

    def __init__(self, service_key: str):
        if not service_key:
            raise AuthConfigError("the gateway provider requires ASTA_GATEWAY_SERVICE_KEY")
        self._service_key = service_key

    @classmethod
    def from_env(cls) -> GatewayProvider:
        return cls(os.environ.get("ASTA_GATEWAY_SERVICE_KEY", "").strip())

    def recognizes(self, request) -> bool:
        parts = (request.headers.get("Authorization") or "").split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return False
        return hmac.compare_digest(parts[1].encode(), self._service_key.encode())

    def authenticate(self, request) -> AuthenticatedUser:
        if not self.recognizes(request):
            raise InvalidCredentialsError("Not the gateway's service key")
        return _gateway_user(request.headers)


def _gateway_user(headers) -> AuthenticatedUser:
    auth0_sub = (headers.get(AUTH0_SUB_HEADER) or "").strip()
    static_key = (headers.get(STATIC_KEY_HEADER) or "").strip()
    user_uuid = (headers.get(USER_UUID_HEADER) or "").strip() or None

    if auth0_sub and static_key:
        raise InvalidCredentialsError("the gateway named both a user and a static key")
    if auth0_sub:
        sub = auth0_sub
    elif static_key:
        sub = f"static-key:{static_key}"
        user_uuid = None
    else:
        raise InvalidCredentialsError("the gateway request names no user")
    if not _SAFE_ID.match(sub):
        raise InvalidCredentialsError("the gateway named a user id this API can't store")

    return AuthenticatedUser(sub=sub, asta_user_uuid=user_uuid)
