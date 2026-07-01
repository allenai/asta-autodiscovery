from __future__ import annotations

from ..base import AuthProvider
from ..models import AuthenticatedUser
from ..permissions import ALL_PERMISSIONS

# The fixed identity used in desktop mode. All permissions so every gated feature
# works, and a stable `sub` so all user-aware business logic keeps functioning.
LOCAL_USER = AuthenticatedUser(
    sub="local",
    permissions=list(ALL_PERMISSIONS),
    email="local@localhost",
    name="Local User",
    email_verified=True,
)


class NoneProvider(AuthProvider):
    """Desktop mode: every request is the same fixed local user.

    authenticate() never raises, so both requires_auth and optional_enrollment
    resolve to the local user.
    """

    name = "none"

    @classmethod
    def from_env(cls) -> NoneProvider:
        return cls()

    def authenticate(self, request) -> AuthenticatedUser:
        return LOCAL_USER
