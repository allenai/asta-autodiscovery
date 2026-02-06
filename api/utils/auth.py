import json
import os
from functools import wraps

import jwt
import requests
from flask import jsonify, request
from jwt.algorithms import RSAAlgorithm

# Cache for Auth0 public keys
_jwks_cache = {}


def get_public_key(auth0_domain, kid):
    """Fetch and cache Auth0 public keys"""
    if kid in _jwks_cache:
        return _jwks_cache[kid]

    jwks_url = f"https://{auth0_domain}/.well-known/jwks.json"
    jwks_response = requests.get(jwks_url)
    jwks = jwks_response.json()

    for key in jwks["keys"]:
        if key["kid"] == kid:
            public_key = RSAAlgorithm.from_jwk(json.dumps(key))
            _jwks_cache[kid] = public_key
            return public_key

    raise ValueError(f"Unable to find key with kid: {kid}")


def verify_token(token, auth0_domain, auth0_audience):
    """Verify JWT token from Auth0"""
    try:
        # Decode header to get kid
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header["kid"]

        # Get public key
        public_key = get_public_key(auth0_domain, kid)

        # Verify and decode token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=auth0_audience,
            issuer=f"https://{auth0_domain}/",
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidAudienceError:
        raise ValueError("Invalid audience")
    except jwt.InvalidIssuerError:
        raise ValueError("Invalid issuer")
    except Exception as e:
        raise ValueError(f"Invalid token: {str(e)}")


def requires_auth(required_permission=None):
    """Decorator to require authentication and optionally a specific permission"""

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            auth0_domain = os.environ.get("AUTH0_DOMAIN")
            auth0_audience = os.environ.get("AUTH0_AUDIENCE")

            if not auth0_domain or not auth0_audience:
                return jsonify({"error": "Auth0 configuration missing"}), 500

            auth_header = request.headers.get("Authorization", None)

            if not auth_header:
                return jsonify({"error": "Authorization header is missing"}), 401

            parts = auth_header.split()
            if parts[0].lower() != "bearer":
                return jsonify({"error": "Authorization header must start with Bearer"}), 401
            elif len(parts) == 1:
                return jsonify({"error": "Token not found"}), 401
            elif len(parts) > 2:
                return jsonify({"error": "Authorization header must be Bearer token"}), 401

            token = parts[1]

            try:
                payload = verify_token(token, auth0_domain, auth0_audience)
                # Dev override: masquerade as another user
                masquerade_user = os.environ.get("DEV_MASQUERADE_USER")
                if masquerade_user:
                    payload["sub"] = masquerade_user
                request.user = payload

                # Check for required permission if specified
                if required_permission:
                    # Permissions are typically in the "permissions" claim as an array
                    permissions = payload.get("permissions", [])

                    if not isinstance(permissions, list):
                        permissions = [permissions]

                    if required_permission not in permissions:
                        return jsonify(
                            {"error": f"Access denied. Required permission: {required_permission}"}
                        ), 403

            except ValueError as e:
                return jsonify({"error": str(e)}), 401

            return f(*args, **kwargs)

        return decorated

    return decorator


def requires_enrollment(f):
    """Decorator that requires authentication with the default permission from AUTH0_REQUIRED_PERMISSION env var.

    This is a convenience wrapper around requires_auth that automatically uses the
    AUTH0_REQUIRED_PERMISSION environment variable (defaulting to "enroll:autodiscovery_v0").

    Usage:
        @requires_default_permission
        def my_route():
            ...
    """
    default_permission = os.environ.get("AUTH0_REQUIRED_PERMISSION", "enroll:autodiscovery_v0")
    return requires_auth(required_permission=default_permission)(f)


def optional_enrollment(f):
    """Decorator that authenticates if a token is present, but allows unauthenticated access.

    If a valid Authorization header is present, validates the token and sets request.user
    (same as requires_enrollment). If no Authorization header is present, sets request.user
    to an empty dict and continues. This enables endpoints to serve both authenticated
    and unauthenticated users (e.g., for shared runs).
    """

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", None)

        if not auth_header:
            request.user = {}
            return f(*args, **kwargs)

        # Token is present, validate it
        auth0_domain = os.environ.get("AUTH0_DOMAIN")
        auth0_audience = os.environ.get("AUTH0_AUDIENCE")

        if not auth0_domain or not auth0_audience:
            return jsonify({"error": "Auth0 configuration missing"}), 500

        parts = auth_header.split()
        if parts[0].lower() != "bearer" or len(parts) != 2:
            request.user = {}
            return f(*args, **kwargs)

        token = parts[1]

        try:
            payload = verify_token(token, auth0_domain, auth0_audience)
            masquerade_user = os.environ.get("DEV_MASQUERADE_USER")
            if masquerade_user:
                payload["sub"] = masquerade_user
            request.user = payload
        except ValueError:
            # Invalid token - treat as unauthenticated
            request.user = {}

        return f(*args, **kwargs)

    return decorated
