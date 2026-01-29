"""Vertex AI OpenAI-compatible clients.

This module provides two adapters:
- VertexOpenAIClientRefresher: for direct OpenAI client usage.
- VertexRefreshingModelClient: for AG2/AutoGen ModelClient usage.
"""

from typing import Any, Dict, List
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
        self._base_url = base_url or get_vertex_openai_base_url()
        self._client = OpenAI(api_key="PLACEHOLDER", base_url=self._base_url, **kwargs)
        self._static_token = (
            api_key
            or os.getenv(VERTEX_ACCESS_TOKEN_ENV)
            or os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN")
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
            raise RuntimeError("google-auth is required to refresh Vertex ADC credentials.") from exc

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


class VertexOpenAIClientRefresher(_VertexADCRefresherBase):
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


class VertexRefreshingModelClient(_VertexADCRefresherBase):
    """AG2 ModelClient that refreshes Vertex AI ADC credentials.

    Use this with AutoGen/AG2 `ModelClient` registration. AG2 expects a `create(params)` method
    plus usage helpers, so this class adapts refresh logic to that interface.

    Reference:
        https://docs.cloud.google.com/vertex-ai/generative-ai/docs/migrate/openai/auth-and-credentials
    """

    def __init__(self, config: Dict[str, Any], **kwargs: Any) -> None:
        """Initialize the Vertex refreshing model client.

        Args:
            config: Model configuration provided by AG2/Autogen.
            **kwargs: Additional keyword arguments (unused).
        """
        self._config = dict(config or {})
        self._base_url = self._config.get("base_url") or get_vertex_openai_base_url()
        self._model = self._config.get("model")
        super().__init__(api_key=None, base_url=self._base_url, **kwargs)

    def create(self, params: Dict[str, Any] | None = None, **kwargs: Any) -> Any:
        """Create a chat completion using refreshed Vertex credentials.

        Args:
            params: Parameters for the OpenAI-compatible chat completion call.
            **kwargs: Additional parameters merged into params.

        Returns:
            OpenAI-compatible response object.
        """
        self._refresh_if_needed()
        merged_params = dict(params or {})
        if kwargs:
            merged_params.update(kwargs)
        if "model" not in merged_params and self._model:
            merged_params["model"] = self._model
        return self._client.chat.completions.create(**merged_params)

    def message_retrieval(self, response: Any) -> List[Any]:
        """Extract messages from a chat completion response.

        Args:
            response: OpenAI-compatible response.

        Returns:
            List of message objects.
        """
        return [choice.message for choice in getattr(response, "choices", [])]

    def cost(self, response: Any) -> float:
        """Return the cost for a response when available.

        Args:
            response: OpenAI-compatible response.

        Returns:
            Cost in USD if known, else 0.0.
        """
        _ = response
        return 0.0

    def get_usage(self, response: Any) -> Dict[str, Any]:
        """Return token usage information from a response.

        Args:
            response: OpenAI-compatible response.

        Returns:
            Usage dict with token counts when available.
        """
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0),
            "completion_tokens": getattr(usage, "completion_tokens", 0),
            "total_tokens": getattr(usage, "total_tokens", 0),
        }
