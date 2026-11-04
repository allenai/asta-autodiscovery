"""Several providers in one deployment, e.g. AUTH_PROVIDER=gateway,auth0."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from .base import AuthProvider, NoCredentialsError
from .models import AuthenticatedUser


class ProviderChain(AuthProvider):
    """Authenticates each request with the first provider that recognizes it.

    Order matters: a provider that recognizes only its own credentials (such
    as ``gateway``) goes before one that takes any bearer (such as ``auth0``).
    The UI's login is the first interactive provider's.
    """

    def __init__(self, providers: Sequence[AuthProvider]):
        if not providers:
            raise ValueError("ProviderChain needs at least one provider")
        self.providers = list(providers)
        self._by_name = {p.name: p for p in self.providers}
        self.primary = next((p for p in self.providers if p.interactive), self.providers[-1])
        self.name = self.primary.name

    @classmethod
    def from_env(cls) -> ProviderChain:
        raise NotImplementedError("built by the factory from AUTH_PROVIDER")

    def authenticate(self, request) -> AuthenticatedUser:
        for provider in self.providers:
            if provider.recognizes(request):
                user = provider.authenticate(request)
                return dataclasses.replace(user, provider=provider.name)
        raise NoCredentialsError("No credentials this deployment accepts")

    def user_profile(self, request, user: AuthenticatedUser) -> dict:
        provider = self._by_name.get(user.provider or "", self.primary)
        return provider.user_profile(request, user)

    def login_with_password(self, username: str, password: str) -> dict | None:
        return self.primary.login_with_password(username, password)

    def public_config(self) -> dict:
        return self.primary.public_config()
