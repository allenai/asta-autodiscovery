from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthenticatedUser:
    """Provider-agnostic identity.

    `sub` is namespaced per provider so GCS paths (users/{sub}/...) stay
    collision-free and recognizable:
        - auth0:         "auth0|...", "google-oauth2|..."
        - password_file: "file|<username>"
        - none:          "local"
    """

    sub: str
    permissions: list[str] = field(default_factory=list)
    email: str | None = None
    name: str | None = None
    picture: str | None = None
    email_verified: bool | None = None

    def to_request_user(self) -> dict:
        """Back-compat dict shape that handlers read via request.user.get(...)."""
        return {
            "sub": self.sub,
            "permissions": self.permissions,
            "email": self.email,
            "name": self.name,
            "picture": self.picture,
            "email_verified": self.email_verified,
        }
