import concurrent.futures
import json
import os
from typing import Any

import boto3
import numpy as np
from pydantic import ValidationError

from autodiscovery import llm
from autodiscovery.llm_usage import UsageTracker


def query_llm(
    messages: list[dict[str, str]],
    n_samples: int,
    model: str = "vertex_ai/gemini-3.1-pro-preview",
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    response_format=None,
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
        temperature: Sampling temperature. Dropped for models that reject it.
        reasoning_effort: Optional reasoning effort. Dropped by litellm for
            models that do not accept it.
        response_format: Optional structured output schema.
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
    if n_samples <= 0:
        return []

    kwargs: dict[str, Any] = {}
    if temperature is not None and llm.accepts_temperature(model):
        kwargs["temperature"] = temperature
    if (effort := llm.normalize_reasoning_effort(model, reasoning_effort)) is not None:
        kwargs["reasoning_effort"] = effort
    if response_format is not None:
        kwargs["response_format"] = response_format

    # Some providers cap n per request, so split the sample count into batches.
    cap = llm.max_n(model)
    batch_sizes = _batch_sizes(n_samples, cap)
    if len(batch_sizes) > 1:
        print(
            f"[query_llm] model={model} requesting n={n_samples} via {len(batch_sizes)} calls "
            f"(max_n={cap})."
        )
        debug_requests = True
    elif debug_requests:
        print(f"[query_llm] model={model} requesting n={n_samples} via 1 call.")

    def _call(batch_n: int):
        if debug_requests:
            print(f"[query_llm] sending request (n={batch_n})")
        return llm.complete(model, messages, n=batch_n, **kwargs)

    if len(batch_sizes) == 1:
        response_items = [(batch_sizes[0], _call(batch_sizes[0]))]
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(batch_sizes))) as pool:
            futures = [(n, pool.submit(_call, n)) for n in batch_sizes]
            response_items = [(n, future.result()) for n, future in futures]

    responses = []
    for batch_n, response in response_items:
        if usage_tracker is not None:
            metadata = dict(usage_metadata or {})
            metadata["n"] = batch_n
            usage_tracker.record_response(
                response,
                source=llm.provider_of(model),
                component=usage_component,
                agent_name=usage_agent_name,
                node_id=usage_node_id,
                metadata=metadata,
            )
        responses.extend(_parse_choices(response, model, response_format))
    return responses


def _batch_sizes(n_samples: int, max_n: int | None) -> list[int]:
    """Split a sample count into per-request batches under a provider's n cap."""
    if max_n is None:
        return [n_samples]
    batches = []
    remaining = n_samples
    while remaining > 0:
        batches.append(min(max_n, remaining))
        remaining -= max_n
    return batches


def _parse_choices(response: Any, model: str, response_format) -> list[Any]:
    """Extract parsed payloads from a litellm response's choices."""
    parsed_responses = []
    for choice in response.choices:
        content = choice.message.content
        if content is None:
            continue
        if response_format is not None:
            try:
                parsed_responses.append(response_format.model_validate_json(content).model_dump())
                continue
            except ValidationError:
                # Fall through to lenient JSON parsing below.
                pass
        try:
            parsed_responses.append(json.loads(content))
        except json.JSONDecodeError:
            if repaired := try_loading_dict(content):
                parsed_responses.append(repaired)
            else:
                raise ValueError(
                    f"LLM response was not valid JSON for model {model}: {content[:200]}"
                ) from None
    return parsed_responses


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
