import concurrent.futures
import json
import os
from typing import Any

import boto3
import numpy as np
from openai import OpenAI
from pydantic import BaseModel, ValidationError

from autodiscovery.llm_retry import call_with_backoff
from autodiscovery.llm_usage import UsageTracker
from autodiscovery.model_spec import ModelSpec, parse_model
from autodiscovery.vertex_client import OpenAICredentialsRefresher
from autodiscovery.vertex_config import VERTEX_ACCESS_TOKEN_ENV, get_vertex_openai_base_url


def normalize_reasoning_effort(spec: ModelSpec, reasoning_effort: str | None) -> str | None:
    """Normalize reasoning effort values across providers.

    Args:
        spec: Resolved model.
        reasoning_effort: Requested reasoning effort value.

    Returns:
        A provider-compatible reasoning effort value or ``None``.
    """
    if reasoning_effort is None:
        return None
    if (
        reasoning_effort == "minimal"
        and spec.is_openai
        and spec.supports_reasoning
        and not spec.supports_minimal_reasoning_effort
    ):
        # Most OpenAI reasoning models take only low/medium/high. Keep CLI
        # semantics consistent by mapping minimal to low, except where litellm
        # records that the model really does accept it (the gpt-5 family).
        print(
            f"[query_llm] model={spec} does not support reasoning_effort='minimal'; "
            "using 'low' instead."
        )
        return "low"
    return reasoning_effort


def get_vertex_access_token() -> str:
    """Return the Vertex AI access token from environment variables.

    Returns:
        The OAuth access token for Vertex AI.

    Raises:
        ValueError: If no access token is configured.
    """
    # Static env tokens bypass ADC refresh. Prefer ADC for long-running jobs.
    token = os.getenv(VERTEX_ACCESS_TOKEN_ENV) or os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN")
    if token:
        return token

    try:
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        credentials.refresh(google.auth.transport.requests.Request())
        if credentials.token:
            return credentials.token
    except Exception:
        pass

    raise ValueError(
        "Vertex AI access token is required for Gemini models. Set "
        f"{VERTEX_ACCESS_TOKEN_ENV} or GOOGLE_OAUTH_ACCESS_TOKEN "
        "to an OAuth access token, or configure Application Default Credentials."
    )


def get_openai_client_for_model(model: str | ModelSpec, api_key: str | None = None) -> Any:
    """Create an OpenAI-compatible client for the given model."""
    spec = model if isinstance(model, ModelSpec) else parse_model(model)
    if spec.is_vertex:
        return OpenAICredentialsRefresher(api_key=api_key, base_url=get_vertex_openai_base_url())
    return OpenAI(api_key=api_key) if api_key else OpenAI()


def query_llm(
    messages: list[dict[str, str]],
    n_samples: int,
    model: str = "gemini-3.1-pro-preview",
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    response_format=None,
    client: Any = None,
    debug_requests: bool = False,
    usage_tracker: UsageTracker | None = None,
    usage_component: str = "query_llm",
    usage_agent_name: str | None = None,
    usage_node_id: str | None = None,
    usage_metadata: dict[str, Any] | None = None,
):
    """Query an LLM and return parsed responses.

    Args:
        messages: Chat messages to send to the model.
        n_samples: Number of samples to request.
        model: Model name, optionally litellm-qualified as ``<provider>/<model>``.
        temperature: Sampling temperature.
        reasoning_effort: Optional reasoning effort for reasoning-capable models.
        response_format: Optional structured output schema.
        client: Optional pre-configured client instance.
        debug_requests: Whether to log request batching details.
        usage_tracker: Optional usage tracker.
        usage_component: Usage component label for tracking.
        usage_agent_name: Optional agent label for tracking.
        usage_node_id: Optional node id for tracking.
        usage_metadata: Optional metadata attached to each usage event.
            The actual per-request sample count is always recorded as ``metadata["n"]``.

    Returns:
        A list of parsed response objects.
    """
    spec = parse_model(model)
    normalized_reasoning_effort = normalize_reasoning_effort(spec, reasoning_effort)

    if spec.is_copilot:
        if response_format is None:
            raise ValueError("Copilot queries require a Pydantic response_format")
        from autodiscovery.copilot_provider import get_copilot_runtime

        runtime = get_copilot_runtime()

        def _sample() -> dict[str, Any]:
            completion = runtime.complete(
                messages=messages,
                model=spec.wire_model_name,
                response_format=response_format,
                temperature=temperature,
                reasoning_effort=normalized_reasoning_effort,
            )
            if usage_tracker is not None:
                metadata = dict(usage_metadata or {})
                metadata["n"] = 1
                metadata["provider_cost"] = completion.usage.provider_cost
                metadata["reasoning_tokens"] = completion.usage.reasoning_tokens
                metadata["cache_read_tokens"] = completion.usage.cache_read_tokens
                metadata["cache_write_tokens"] = completion.usage.cache_write_tokens
                usage_tracker.record_event(
                    source="copilot",
                    component=usage_component,
                    model=completion.usage.model,
                    prompt_tokens=completion.usage.input_tokens,
                    completion_tokens=completion.usage.output_tokens,
                    total_tokens=completion.usage.total_tokens,
                    agent_name=usage_agent_name,
                    node_id=usage_node_id,
                    metadata=metadata,
                )
            return response_format.model_validate_json(completion.content).model_dump()

        if n_samples <= 0:
            return []
        responses = [_sample()]
        if n_samples > 1:
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(8, n_samples - 1)
            ) as executor:
                responses.extend(executor.map(lambda _: _sample(), range(n_samples - 1)))
        return responses

    if client is None:
        client = get_openai_client_for_model(spec)
    model_name = spec.wire_model_name

    max_n = spec.max_n
    if max_n is not None:
        batch_sizes = []
        remaining = n_samples
        while remaining > 0:
            batch = min(max_n, remaining)
            batch_sizes.append(batch)
            remaining -= batch
    else:
        batch_sizes = [n_samples]

    if len(batch_sizes) > 1:
        print(
            f"[query_llm] model={model} requesting n={n_samples} via {len(batch_sizes)} calls "
            f"(max_n={max_n})."
        )
        debug_requests = True
    elif debug_requests:
        print(f"[query_llm] model={model} requesting n={n_samples} via 1 call.")

    request_counter = {"sent": 0}

    def _call_llm(batch_n: int):
        if debug_requests:
            request_counter["sent"] += 1
            print(
                f"[query_llm] sending request {request_counter['sent']}/{len(batch_sizes)} "
                f"(n={batch_n})"
            )
        kwargs = {
            "model": model_name,
            "messages": messages,
            "n": batch_n,
        }
        if temperature is not None and spec.accepts_temperature:
            kwargs["temperature"] = temperature

        if spec.supports_reasoning and normalized_reasoning_effort is not None:
            kwargs["reasoning_effort"] = normalized_reasoning_effort

        def _send_request():
            try:
                if response_format is not None:
                    return client.beta.chat.completions.parse(
                        **kwargs, response_format=response_format
                    )
                return client.chat.completions.create(**kwargs)
            except ValidationError:
                # Retry if the response format validation fails
                return client.beta.chat.completions.parse(**kwargs, response_format=response_format)

        return call_with_backoff(
            _send_request,
            label=f"query_llm(model={model_name}, n={batch_n})",
        )

    responses = []
    response_items: list[tuple[int, Any]] = []
    if len(batch_sizes) == 1:
        batch_n = batch_sizes[0]
        response_items = [(batch_n, _call_llm(batch_n))]
    elif spec.is_vertex:
        max_workers = min(8, len(batch_sizes))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [(batch_n, executor.submit(_call_llm, batch_n)) for batch_n in batch_sizes]
            response_items = [(batch_n, future.result()) for batch_n, future in futures]
    else:
        response_items = [(batch_n, _call_llm(batch_n)) for batch_n in batch_sizes]

    for batch_n, response in response_items:
        if usage_tracker is not None:
            metadata = dict(usage_metadata or {})
            metadata["n"] = batch_n
            usage_tracker.record_response(
                response,
                source="openai",
                component=usage_component,
                agent_name=usage_agent_name,
                node_id=usage_node_id,
                metadata=metadata,
            )
        for choice in response.choices:
            if response_format is not None and getattr(choice.message, "parsed", None) is not None:
                parsed = choice.message.parsed
                if isinstance(parsed, BaseModel):
                    responses.append(parsed.model_dump())
                else:
                    responses.append(parsed)
                continue
            if choice.message.content is None:
                continue
            try:
                responses.append(json.loads(choice.message.content))
            except json.JSONDecodeError:
                parsed = try_loading_dict(choice.message.content)
                if parsed:
                    responses.append(parsed)
                else:
                    preview = choice.message.content[:200]
                    raise ValueError(
                        f"LLM response was not valid JSON for model {model}: {preview}"
                    )
    return responses


def try_loading_dict(_dict_str):
    try:
        return json.loads(_dict_str)
    except json.JSONDecodeError:
        try:
            return json.loads(_dict_str + '"}')  # Fix case where string is truncated
        except json.JSONDecodeError:
            return {}


def fuse_gaussians(means, stds, weight=1.0):
    """Fuse n independent Gaussian beliefs N(mu_i, sigma_i^2)
    into a single Gaussian via product of Gaussians.

    Parameters
    ----------
    means : array-like, shape (n,)
        The means μ_i of the Gaussian beliefs.
    stds : array-like, shape (n,)
        The standard deviations σ_i of the Gaussian beliefs.
    weight : float, optional
        A weight to apply to the precision of each Gaussian. Default is 1.0.

    Returns:
    -------
    mu_star : float
        The fused mean μ_*.
    sigma_star : float
        The fused standard deviation σ_*.
    """
    means = np.array(means, dtype=float)
    variances = (
        np.array(stds, dtype=float) ** 2 + 1e-10
    )  # Add small value to avoid division by zero

    # Precisions
    precisions = weight / variances

    # Combined precision and variance
    precision_star = np.sum(precisions)
    variance_star = 1.0 / precision_star

    # Combined mean
    mu_star = np.sum(precisions * means) / precision_star
    sigma_star = np.sqrt(variance_star)

    return mu_star, sigma_star


def fetch_from_s3(links: list[str], download_dir="_s3") -> list[str]:
    """Download data from S3 URLs
    Attributes:
        links (List[str]): List of S3 URLs to download
        download_dir (str): Directory to save downloaded files
    Returns:
        List of local file paths where files are downloaded
    """
    s3_client = boto3.client("s3")
    fpaths = []
    for link in links:
        _, _, bucket, key = link.split("/", 3)
        local_file_path = os.path.join(download_dir, key)
        local_dir = os.path.dirname(local_file_path)
        os.makedirs(local_dir, exist_ok=True)
        byte_str = s3_client.get_object(Bucket=bucket, Key=key)["Body"].read()
        with open(local_file_path, "wb") as file:
            file.write(byte_str)
        fpaths.append(local_file_path)

    return fpaths
