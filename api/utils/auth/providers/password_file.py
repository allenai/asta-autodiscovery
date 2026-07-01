from __future__ import annotations

import os
import time

import jwt

from ..base import AuthConfigError, AuthProvider, InvalidCredentialsError
from ..models import AuthenticatedUser
from ..password_store import PasswordStore
from ._bearer import extract_bearer_token

_ALGORITHM = "HS256"
_DEFAULT_TTL_SECONDS = 12 * 60 * 60  # 12h


def _sub_for(username: str) -> str:
    return f"file|{username}"


class PasswordFileProvider(AuthProvider):
    """user:password file provider.

    Login (POST /api/auth/login) verifies the password against the file *once*
    and issues a short-lived HS256 session token. On every subsequent request
    authenticate() verifies the token signature and then re-reads the file to
    confirm the user still exists / is enabled and to load their *current*
    permissions. So new users can log in immediately, permission/enable changes
    take effect on the next request, and deleted users are locked out on their
    next request — all without restarting the web stack.
    """

    name = "password_file"

    def __init__(self, file_path: str | None, secret: str | None, ttl_seconds: int):
        self.file_path = file_path
        self.secret = secret
        self.ttl_seconds = ttl_seconds

    @classmethod
    def from_env(cls) -> PasswordFileProvider:
        ttl = os.environ.get("AUTH_SESSION_TTL")
        return cls(
            file_path=os.environ.get("AUTH_PASSWORD_FILE"),
            secret=os.environ.get("AUTH_SESSION_SECRET"),
            ttl_seconds=int(ttl) if ttl else _DEFAULT_TTL_SECONDS,
        )

    def _store(self) -> PasswordStore:
        if not self.file_path or not self.secret:
            raise AuthConfigError(
                "password_file provider requires AUTH_PASSWORD_FILE and AUTH_SESSION_SECRET"
            )
        return PasswordStore(self.file_path)

    def authenticate(self, request) -> AuthenticatedUser:
        store = self._store()
        token = extract_bearer_token(request)
        try:
            claims = jwt.decode(token, self.secret, algorithms=[_ALGORITHM])
        except jwt.ExpiredSignatureError:
            raise InvalidCredentialsError("Session has expired") from None
        except jwt.InvalidTokenError as e:
            raise InvalidCredentialsError(f"Invalid session token: {e}") from e

        username = claims.get("username")
        # Re-read the file every request: the token alone is not sufficient.
        record = store.get_user(username) if username else None
        if not record or record.get("disabled"):
            raise InvalidCredentialsError("User no longer active")

        return AuthenticatedUser(
            sub=_sub_for(username),
            permissions=list(record.get("permissions", [])),
            email=record.get("email"),
            name=record.get("name"),
            email_verified=True,
        )

    def login_with_password(self, username: str, password: str) -> dict | None:
        """Verify credentials against the file and mint a session token.

        Returns {"token", "expires_at"} on success, or None on bad credentials.
        """
        store = self._store()
        record = store.verify_credentials(username, password)
        if record is None:
            return None

        now = int(time.time())
        expires_at = now + self.ttl_seconds
        claims = {
            "sub": _sub_for(username),
            "username": username,
            "name": record.get("name"),
            "email": record.get("email"),
            # Included for client-side UI gating only; the backend always re-reads
            # the file for authoritative permission checks.
            "permissions": list(record.get("permissions", [])),
            "iat": now,
            "exp": expires_at,
        }
        token = jwt.encode(claims, self.secret, algorithm=_ALGORITHM)
        return {"token": token, "expires_at": expires_at}
