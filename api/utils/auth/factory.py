import os

from .base import AuthConfigError, AuthProvider

_PROVIDER_CACHE: AuthProvider | None = None


def _build_provider() -> AuthProvider:
    kind = os.environ.get("AUTH_PROVIDER", "auth0").strip().lower()

    # Imported lazily so a deployment only needs the dependencies of the
    # provider it actually uses.
    if kind == "auth0":
        from .providers.auth0 import Auth0Provider

        return Auth0Provider.from_env()
    if kind == "password_file":
        from .providers.password_file import PasswordFileProvider

        return PasswordFileProvider.from_env()
    if kind == "none":
        from .providers.none import NoneProvider

        return NoneProvider.from_env()

    raise AuthConfigError(
        f"Unknown AUTH_PROVIDER '{kind}'. Expected 'auth0', 'password_file', or 'none'."
    )


def get_auth_provider() -> AuthProvider:
    """Return the process-wide auth provider, constructed once from the environment."""
    global _PROVIDER_CACHE
    if _PROVIDER_CACHE is None:
        _PROVIDER_CACHE = _build_provider()
    return _PROVIDER_CACHE


def reset_auth_provider() -> None:
    """Clear the cached provider (used by tests / after env changes)."""
    global _PROVIDER_CACHE
    _PROVIDER_CACHE = None
