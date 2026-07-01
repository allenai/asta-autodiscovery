import os
from functools import wraps

from flask import g, jsonify, request

from utils.userid_logging import set_userid

from .base import AuthConfigError, InvalidCredentialsError, NoCredentialsError
from .factory import get_auth_provider
from .models import AuthenticatedUser
from .permissions import PermissionType


def _establish_user(user: AuthenticatedUser) -> dict:
    """Set request.user (back-compat dict) and the logging context."""
    request_user = user.to_request_user()
    request.user = request_user
    request.auth_user = user  # typed identity, for provider.user_profile()
    g._userid_logging_token = set_userid(request_user.get("sub"))
    return request_user


def requires_auth(
    required_permission=None,
    check_permissions: list[PermissionType] = [],
):
    """Require authentication and optionally check specific permissions."""

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            try:
                user = get_auth_provider().authenticate(request)
            except AuthConfigError as e:
                return jsonify({"error": str(e)}), 500
            except (NoCredentialsError, InvalidCredentialsError) as e:
                return jsonify({"error": str(e)}), 401

            request_user = _establish_user(user)
            permissions = request_user.get("permissions", [])
            if not isinstance(permissions, list):
                permissions = [permissions]

            if required_permission and required_permission not in permissions:
                return jsonify(
                    {"error": f"Access denied. Required permission: {required_permission}"}
                ), 403

            if check_permissions:
                for perm_type in check_permissions:
                    setattr(request, perm_type.value, perm_type.value in permissions)

            return f(*args, **kwargs)

        return decorated

    return decorator


def requires_enrollment(f):
    """Require authentication with the default permission from the environment.

    Convenience wrapper around requires_auth that uses AUTH_REQUIRED_PERMISSION
    (falling back to AUTH0_REQUIRED_PERMISSION). If neither is set, no specific
    permission is required.
    """
    default_permission = (
        os.environ.get("AUTH_REQUIRED_PERMISSION")
        or os.environ.get("AUTH0_REQUIRED_PERMISSION")
        or None
    )
    return requires_auth(required_permission=default_permission)(f)


def optional_enrollment(f):
    """Authenticate if credentials are present, else continue anonymously.

    On valid credentials, behaves like requires_enrollment (sets request.user).
    On missing or invalid credentials, sets request.user to {} and continues, so
    endpoints can serve both authenticated and anonymous users (e.g. shared runs).
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            user = get_auth_provider().authenticate(request)
        except AuthConfigError as e:
            return jsonify({"error": str(e)}), 500
        except (NoCredentialsError, InvalidCredentialsError):
            request.user = {}
            return f(*args, **kwargs)

        _establish_user(user)
        return f(*args, **kwargs)

    return decorated
