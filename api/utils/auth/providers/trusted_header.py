"""Requests relayed by a trusted upstream that has already authenticated the user.

An authenticating proxy or API gateway in front of this API signs its users in
itself, then forwards their requests with a shared secret as the bearer and
names the user in a header. Such headers are trusted only on a request that
carries the secret; the upstream must drop any copy its own callers send.

Configuration:

    AUTH_TRUSTED_HEADER_SECRET   the bearer the upstream sends (required)
    AUTH_TRUSTED_HEADER_USER     the header(s) naming the user, default
                                 X-Forwarded-User

``AUTH_TRUSTED_HEADER_USER`` may list several headers, separated by commas,
each optionally ``header=prefix``. A request must carry exactly one of them;
its value, after the prefix, is the user id. A prefix keeps kinds of caller
apart, e.g. ``X-Forwarded-User,X-Forwarded-Service=service:``.

Callers authenticated this way hold no permissions. The provider recognizes
only requests bearing the secret, so it goes before a provider that takes
every request: AUTH_PROVIDER=trusted_header,auth0.
"""

from __future__ import annotations

import hmac
import os
import re
from collections.abc import Sequence

from ..base import AuthConfigError, AuthProvider, InvalidCredentialsError
from ..models import AuthenticatedUser

DEFAULT_USER_HEADER = "X-Forwarded-User"

# A user id becomes a storage prefix (users/{sub}/), so it must be one path
# segment.
_SAFE_ID = re.compile(r"^[A-Za-z0-9|_.@:+-]+$")
_HEADER_NAME = re.compile(r"^[A-Za-z0-9-]+$")


def parse_user_headers(spec: str) -> list[tuple[str, str]]:
    """Parse ``header[=prefix],...`` into (header, prefix) pairs."""
    pairs = []
    for item in spec.split(","):
        item = item.strip()
        if not item:
            continue
        header, _, prefix = item.partition("=")
        header = header.strip()
        if not _HEADER_NAME.match(header):
            raise AuthConfigError(f"AUTH_TRUSTED_HEADER_USER: '{header}' is not a header name")
        pairs.append((header, prefix.strip()))
    if not pairs:
        raise AuthConfigError("AUTH_TRUSTED_HEADER_USER names no header")
    if len({h.lower() for h, _ in pairs}) != len(pairs):
        raise AuthConfigError("AUTH_TRUSTED_HEADER_USER names a header twice")
    return pairs


class TrustedHeaderProvider(AuthProvider):
    name = "trusted_header"
    interactive = False

    def __init__(self, secret: str, user_headers: Sequence[tuple[str, str]]):
        if not secret:
            raise AuthConfigError("the trusted_header provider requires AUTH_TRUSTED_HEADER_SECRET")
        self._secret = secret.encode()
        self._user_headers = list(user_headers)

    @classmethod
    def from_env(cls) -> TrustedHeaderProvider:
        return cls(
            os.environ.get("AUTH_TRUSTED_HEADER_SECRET", "").strip(),
            parse_user_headers(os.environ.get("AUTH_TRUSTED_HEADER_USER", DEFAULT_USER_HEADER)),
        )

    def recognizes(self, request) -> bool:
        parts = (request.headers.get("Authorization") or "").split()
        if len(parts) != 2 or parts[0].lower() != "bearer":
            return False
        return hmac.compare_digest(parts[1].encode(), self._secret)

    def authenticate(self, request) -> AuthenticatedUser:
        if not self.recognizes(request):
            raise InvalidCredentialsError("Not the trusted upstream's secret")

        named = [
            (prefix, value)
            for header, prefix in self._user_headers
            if (value := (request.headers.get(header) or "").strip())
        ]
        if not named:
            raise InvalidCredentialsError("the request names no user")
        if len(named) > 1:
            raise InvalidCredentialsError("the request names more than one user")

        prefix, value = named[0]
        sub = f"{prefix}{value}"
        if not _SAFE_ID.match(sub):
            raise InvalidCredentialsError("the request names a user id this API can't store")
        return AuthenticatedUser(sub=sub)
