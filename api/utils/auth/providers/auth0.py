from __future__ import annotations

import json
import os

import jwt
import requests
from jwt.algorithms import RSAAlgorithm

from ..base import AuthConfigError, AuthProvider, InvalidCredentialsError
from ..models import AuthenticatedUser
from ._bearer import extract_bearer_token

# Cache for Auth0 public keys (by kid).
_jwks_cache: dict = {}


def get_public_key(auth0_domain: str, kid: str):
    """Fetch and cache an Auth0 public key by key id."""
    if kid in _jwks_cache:
        return _jwks_cache[kid]

    jwks_url = f"https://{auth0_domain}/.well-known/jwks.json"
    jwks = requests.get(jwks_url).json()

    for key in jwks["keys"]:
        if key["kid"] == kid:
            public_key = RSAAlgorithm.from_jwk(json.dumps(key))
            _jwks_cache[kid] = public_key
            return public_key

    raise ValueError(f"Unable to find key with kid: {kid}")


def verify_token(token: str, auth0_domain: str, auth0_audience: str) -> dict:
    """Verify a JWT issued by Auth0."""
    try:
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header["kid"]
        public_key = get_public_key(auth0_domain, kid)
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=auth0_audience,
            issuer=f"https://{auth0_domain}/",
        )
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidAudienceError:
        raise ValueError("Invalid audience")
    except jwt.InvalidIssuerError:
        raise ValueError("Invalid issuer")
    except Exception as e:
        raise ValueError(f"Invalid token: {str(e)}")


class Auth0Provider(AuthProvider):
    name = "auth0"

    def __init__(self, domain: str | None, audience: str | None, required_permission: str | None):
        self.domain = domain
        self.audience = audience
        self.required_permission = required_permission

    @classmethod
    def from_env(cls) -> Auth0Provider:
        # Read lazily here but validate at authenticate() time so a missing config
        # produces the same per-request 500 the original implementation returned.
        return cls(
            domain=os.environ.get("AUTH0_DOMAIN"),
            audience=os.environ.get("AUTH0_AUDIENCE"),
            required_permission=(
                os.environ.get("AUTH_REQUIRED_PERMISSION")
                or os.environ.get("AUTH0_REQUIRED_PERMISSION")
                or None
            ),
        )

    def authenticate(self, request) -> AuthenticatedUser:
        if not self.domain or not self.audience:
            raise AuthConfigError("Auth0 configuration missing")

        token = extract_bearer_token(request)
        try:
            payload = verify_token(token, self.domain, self.audience)
        except ValueError as e:
            raise InvalidCredentialsError(str(e)) from e

        permissions = payload.get("permissions", [])
        if not isinstance(permissions, list):
            permissions = [permissions]

        return AuthenticatedUser(
            sub=payload.get("sub"),
            permissions=permissions,
            email=payload.get("email"),
            name=payload.get("name"),
            picture=payload.get("picture"),
            email_verified=payload.get("email_verified"),
        )

    def user_profile(self, request, user: AuthenticatedUser) -> dict:
        """Fetch the full profile from Auth0 /userinfo (access token has basic claims)."""
        token = extract_bearer_token(request)
        userinfo_url = f"https://{self.domain}/userinfo"
        resp = requests.get(userinfo_url, headers={"Authorization": f"Bearer {token}"})
        resp.raise_for_status()
        info = resp.json()
        return {
            "sub": info.get("sub"),
            "name": info.get("name"),
            "email": info.get("email"),
            "picture": info.get("picture"),
            "email_verified": info.get("email_verified"),
        }

    def public_config(self) -> dict:
        return {
            "provider": self.name,
            "domain": self.domain,
            "clientId": os.environ.get("AUTH0_CLIENT_ID"),
            "audience": self.audience,
            "requiredPermission": self.required_permission,
        }
