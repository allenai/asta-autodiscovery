import os

import pytest


def test_ag2_gemini_client_available():
    """Ensure AG2's Gemini client can be constructed (deps installed)."""
    from autogen.oai.client import OpenAIWrapper
    from autogen.oai.gemini import GeminiClient

    wrapper = OpenAIWrapper(
        config_list=[
            {
                "api_type": "google",
                "model": "gemini-3-flash-preview",
                "api_key": "test-api-key",
            }
        ]
    )
    assert wrapper._clients
    assert isinstance(wrapper._clients[0], GeminiClient)


@pytest.mark.adc
def test_ag2_gemini_client_adc_integration():
    """Ensure AG2's Gemini client can make a real request via ADC."""
    if os.getenv("GOOGLE_GEMINI_API_KEY"):
        pytest.skip("GOOGLE_GEMINI_API_KEY is set; ADC path not exercised.")
    if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        pytest.skip("GOOGLE_APPLICATION_CREDENTIALS is not set.")
    project_id = os.getenv("VERTEX_PROJECT_ID") or os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("VERTEX_LOCATION")
    if not project_id or not location:
        pytest.skip("VERTEX_PROJECT_ID/GOOGLE_CLOUD_PROJECT or VERTEX_LOCATION not set.")

    from autogen.oai.client import OpenAIWrapper
    from autogen.oai.gemini import GeminiClient

    model = os.getenv("VERTEX_TEST_MODEL", "gemini-3-flash-preview")
    wrapper = OpenAIWrapper(
        config_list=[
            {
                "api_type": "google",
                "model": model,
                "project_id": project_id,
                "location": location,
                "google_application_credentials": os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
            }
        ]
    )
    assert wrapper._clients
    assert isinstance(wrapper._clients[0], GeminiClient)

    response = wrapper.create(messages=[{"role": "user", "content": "ping"}], max_tokens=8)
    assert response is not None
    assert getattr(response, "choices", None) is not None
