"""Vertex AI OpenAI-compatible clients.

This module provides a client adapter for direct OpenAI client usage.
"""

from typing import Any
import os
import threading

from openai import OpenAI

from autodiscovery.vertex_config import VERTEX_ACCESS_TOKEN_ENV, get_vertex_openai_base_url


class _VertexADCRefresherBase:
    """Shared ADC refresh logic for Vertex AI OpenAI-compatible clients."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, **kwargs: Any):
        """Initialize shared OpenAI client and ADC refresh state.

        Args:
            api_key: Optional static token to use instead of ADC.
            base_url: Optional Vertex OpenAI-compatible base URL override.
            **kwargs: Additional keyword arguments for OpenAI client.
        """
        normalized_base_url = base_url if base_url is None else str(base_url)
        self._base_url = normalized_base_url or get_vertex_openai_base_url()
        self._client = OpenAI(api_key="PLACEHOLDER", base_url=self._base_url, **kwargs)
        self._static_token = (
            api_key or os.getenv(VERTEX_ACCESS_TOKEN_ENV) or os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN")
        )
        self._creds = None
        self._request = None
        self._lock = threading.Lock()

        if not self._static_token:
            self._init_adc()

    def _init_adc(self) -> None:
        try:
            import google.auth
            import google.auth.transport.requests
        except Exception as exc:
            raise RuntimeError(
                "google-auth is required to refresh Vertex ADC credentials."
            ) from exc

        self._creds, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        self._request = google.auth.transport.requests.Request()

    def _refresh_if_needed(self) -> None:
        """Refresh ADC credentials when needed."""
        with self._lock:
            if self._static_token:
                self._client.api_key = self._static_token
                return

            if self._creds is None or self._request is None:
                raise RuntimeError("Vertex ADC credentials are not configured.")

            if not self._creds.valid:
                self._creds.refresh(self._request)

            if not self._creds.valid or not self._creds.token:
                raise RuntimeError("Unable to refresh Vertex ADC credentials.")

            self._client.api_key = self._creds.token


class OpenAICredentialsRefresher(_VertexADCRefresherBase):
    """OpenAI client wrapper that refreshes Vertex AI ADC credentials.

    Use this when code calls `client.chat.completions.create(...)` directly (e.g., query_llm,
    image analysis). It provides an OpenAI-like interface via __getattr__ and refreshes tokens
    before delegating to the underlying OpenAI client.

    Reference:
        https://docs.cloud.google.com/vertex-ai/generative-ai/docs/migrate/openai/auth-and-credentials
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None, **kwargs: Any):
        """Initialize the refreshing OpenAI client wrapper.

        Args:
            api_key: Optional static token to use instead of ADC.
            base_url: Optional Vertex OpenAI-compatible base URL override.
            **kwargs: Additional keyword arguments for OpenAI client.
        """
        super().__init__(api_key=api_key, base_url=base_url, **kwargs)

    def __getattr__(self, name: str) -> Any:
        self._refresh_if_needed()
        return getattr(self._client, name)
