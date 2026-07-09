"""Swappable authentication.

Public API preserved from the original ``utils.auth`` module so existing call
sites (``from utils.auth import requires_auth, optional_enrollment, ...``) keep
working. The active provider is selected by the AUTH_PROVIDER env var.
"""

from .base import (
    AuthConfigError,
    AuthError,
    AuthProvider,
    InvalidCredentialsError,
    NoCredentialsError,
)
from .decorators import optional_enrollment, requires_auth
from .factory import get_auth_provider, reset_auth_provider
from .models import AuthenticatedUser
from .permissions import ALL_PERMISSIONS, PermissionType

__all__ = [
    "ALL_PERMISSIONS",
    "AuthConfigError",
    "AuthError",
    "AuthProvider",
    "AuthenticatedUser",
    "InvalidCredentialsError",
    "NoCredentialsError",
    "PermissionType",
    "get_auth_provider",
    "optional_enrollment",
    "requires_auth",
    "reset_auth_provider",
]
