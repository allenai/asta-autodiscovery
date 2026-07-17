from ..base import InvalidCredentialsError, NoCredentialsError


def extract_bearer_token(request) -> str:
    """Return the Bearer token from the Authorization header.

    Raises NoCredentialsError if the header is absent, InvalidCredentialsError if
    it is malformed. Mirrors the original requires_auth header parsing.
    """
    auth_header = request.headers.get("Authorization", None)
    if not auth_header:
        raise NoCredentialsError("Authorization header is missing")

    parts = auth_header.split()
    if parts[0].lower() != "bearer":
        raise InvalidCredentialsError("Authorization header must start with Bearer")
    if len(parts) == 1:
        raise InvalidCredentialsError("Token not found")
    if len(parts) > 2:
        raise InvalidCredentialsError("Authorization header must be Bearer token")

    return parts[1]
