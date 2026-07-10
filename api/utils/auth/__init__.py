"""Swappable authentication.

Public API preserved from the original ``utils.auth`` module so existing call
sites (``from utils.auth import requires_auth, optional_enrollment, ...``) keep
working. The active provider is selected by the AUTH_PROVIDER env var.

The re-exports are resolved lazily (PEP 562) so that importing a lightweight
submodule such as ``utils.auth.password_store`` (used by the admin CLI) does not
pull in Flask and the rest of the request-path dependencies.
"""

import importlib

# name -> submodule it lives in
_EXPORTS = {
    "AuthConfigError": ".base",
    "AuthError": ".base",
    "AuthProvider": ".base",
    "InvalidCredentialsError": ".base",
    "NoCredentialsError": ".base",
    "optional_enrollment": ".decorators",
    "requires_auth": ".decorators",
    "get_auth_provider": ".factory",
    "reset_auth_provider": ".factory",
    "AuthenticatedUser": ".models",
    "ALL_PERMISSIONS": ".permissions",
    "PermissionType": ".permissions",
}

__all__ = sorted(_EXPORTS)


def __getattr__(name: str):
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(importlib.import_module(module, __name__), name)


def __dir__():
    return sorted(list(globals()) + __all__)
