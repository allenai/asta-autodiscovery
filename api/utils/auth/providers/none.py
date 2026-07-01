from __future__ import annotations

import os

from ..base import AuthProvider
from ..models import AuthenticatedUser
from ..permissions import ALL_PERMISSIONS


class NoneProvider(AuthProvider):
    """Desktop mode: every request is the same fixed local user.

    authenticate() never raises, so both requires_auth and optional_enrollment
    resolve to the local user. The user carries all permissions so every gated
    feature works, and all user-aware business logic receives a stable `sub`.
    """

    name = "none"

    def __init__(self, sub: str, name: str, email: str):
        self.local_user = AuthenticatedUser(
            sub=sub,
            permissions=list(ALL_PERMISSIONS),
            email=email,
            name=name,
            email_verified=True,
        )

    @classmethod
    def from_env(cls) -> NoneProvider:
        return cls(
            sub=os.environ.get("AUTH_LOCAL_SUB", "local"),
            name=os.environ.get("AUTH_LOCAL_NAME", "Local User"),
            email=os.environ.get("AUTH_LOCAL_EMAIL", "local@localhost"),
        )

    def authenticate(self, request) -> AuthenticatedUser:
        return self.local_user
