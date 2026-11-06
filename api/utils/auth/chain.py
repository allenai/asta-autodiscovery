"""Several auth providers in one deployment (comma-separated AUTH_PROVIDER)."""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence

from .base import AuthConfigError, AuthProvider, NoCredentialsError
from .models import AuthenticatedUser


def _is_selective(provider: AuthProvider) -> bool:
    return type(provider).recognizes is not AuthProvider.recognizes


class ProviderChain(AuthProvider):
    """Authenticates each request with the first provider that recognizes it.

    Only the last provider may recognize every request. The UI's login is the
    first interactive provider's.
    """

    def __init__(self, providers: Sequence[AuthProvider]):
        if not providers:
            raise ValueError("ProviderChain needs at least one provider")
        for provider in providers[:-1]:
            if not _is_selective(provider):
                raise AuthConfigError(
                    f"AUTH_PROVIDER: '{provider.name}' accepts every request, so it must "
                    "come last; the providers after it would never be used"
                )
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
