from __future__ import annotations

from abc import ABC, abstractmethod

from .models import AuthenticatedUser


class AuthError(Exception):
    """Base class for authentication failures surfaced to the client."""


class NoCredentialsError(AuthError):
    """No credentials were presented on the request."""


class InvalidCredentialsError(AuthError):
    """Credentials were presented but are invalid (bad/expired token, etc.)."""


class AuthConfigError(AuthError):
    """The active provider is misconfigured (maps to HTTP 500)."""


class AuthProvider(ABC):
    """A swappable authentication backend.

    Implementations validate the credentials carried on an incoming request and
    return a normalized AuthenticatedUser. The three decorators in
    ``utils.auth.decorators`` translate the outcome into HTTP behavior.
    """

    #: Stable identifier reported to the UI via /api/auth/config.
    name: str

    @classmethod
    @abstractmethod
    def from_env(cls) -> AuthProvider:
        """Construct the provider from environment configuration."""

    @abstractmethod
    def authenticate(self, request) -> AuthenticatedUser:
        """Validate the request's credentials.

        Raise NoCredentialsError if none are present, InvalidCredentialsError if
        present-but-invalid. Otherwise return the authenticated user.
        """

    def user_profile(self, request, user: AuthenticatedUser) -> dict:
        """Full profile for GET /api/user/me. Defaults to the normalized identity."""
        return user.to_request_user()

    def login_with_password(self, username: str, password: str) -> dict | None:
        """Password login. Only the password_file provider supports this."""
        raise NotImplementedError(f"Provider '{self.name}' does not support password login")

    def public_config(self) -> dict:
        """Non-secret descriptor the UI fetches to choose its login UI."""
        return {"provider": self.name}
