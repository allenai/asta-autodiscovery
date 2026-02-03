"""Shared Vertex AI configuration helpers."""

import os

VERTEX_OPENAI_BASE_URL_ENV = "VERTEX_OPENAI_BASE_URL"
VERTEX_ACCESS_TOKEN_ENV = "VERTEX_ACCESS_TOKEN"
VERTEX_PROJECT_ENV_VAR = "VERTEX_PROJECT_ID"
VERTEX_LOCATION_ENV_VAR = "VERTEX_LOCATION"


def get_vertex_openai_base_url() -> str:
    """Return the Vertex AI OpenAI-compatible base URL.

    Returns:
        The Vertex AI OpenAI-compatible base URL.

    Raises:
        ValueError: If required project or location settings are missing.
    """
    # Reference: https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/chat-completions/intro_chat_completions_api.ipynb
    explicit_base_url = os.getenv(VERTEX_OPENAI_BASE_URL_ENV)
    if explicit_base_url:
        return explicit_base_url

    project_id = os.getenv(VERTEX_PROJECT_ENV_VAR)
    location = os.getenv(VERTEX_LOCATION_ENV_VAR) or "global"

    if not project_id:
        raise ValueError(
            "Vertex AI configuration is required for Gemini models. Set "
            f"{VERTEX_OPENAI_BASE_URL_ENV} or both a project ID "
            f"({VERTEX_PROJECT_ENV_VAR}) and an optional location "
            f"({VERTEX_LOCATION_ENV_VAR}, defaults to global)."
        )

    api_host = (
        "aiplatform.googleapis.com"
        if location == "global"
        else f"{location}-aiplatform.googleapis.com"
    )
    return f"https://{api_host}/v1/projects/{project_id}/locations/{location}/endpoints/openapi"
