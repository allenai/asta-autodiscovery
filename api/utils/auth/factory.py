import os

from .base import AuthConfigError, AuthProvider

_PROVIDER_CACHE: AuthProvider | None = None

_KNOWN = ("auth0", "password_file", "none")


def _build_one(kind: str) -> AuthProvider:
    # Imported lazily so a deployment only needs the dependencies of the
    # providers it actually uses.
    if kind == "auth0":
        from .providers.auth0 import Auth0Provider

        return Auth0Provider.from_env()
    if kind == "password_file":
        from .providers.password_file import PasswordFileProvider

        return PasswordFileProvider.from_env()
    if kind == "none":
        from .providers.none import NoneProvider

        return NoneProvider.from_env()

    expected = ", ".join(f"'{k}'" for k in _KNOWN)
    raise AuthConfigError(f"Unknown AUTH_PROVIDER '{kind}'. Expected {expected}.")


def _build_provider() -> AuthProvider:
    """AUTH_PROVIDER names one provider, or several separated by commas.

    With several, each request goes to the first, in order, that recognizes its
    credentials (see ProviderChain).
    """
    kinds = [k.strip().lower() for k in os.environ.get("AUTH_PROVIDER", "none").split(",")]
    kinds = [k for k in kinds if k] or ["none"]
    if len(set(kinds)) != len(kinds):
        raise AuthConfigError(f"AUTH_PROVIDER names a provider twice: {','.join(kinds)}")
    providers = [_build_one(k) for k in kinds]
    if len(providers) == 1:
        return providers[0]

    from .chain import ProviderChain

    return ProviderChain(providers)


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
