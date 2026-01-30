import os
import json
from typing import Any, Dict, List
import concurrent.futures

import numpy as np
import boto3
from pydantic import ValidationError
from pydantic import BaseModel
from openai import OpenAI

from autodiscovery.vertex_config import VERTEX_ACCESS_TOKEN_ENV, get_vertex_openai_base_url
from autodiscovery.vertex_client import OpenAICredentialsRefresher


def is_gemini_model(model: str) -> bool:
    """Check if the model is a Gemini model."""
    if not model:
        return False
    return model.split("/")[-1].startswith("gemini")


def is_reasoning_model(model: str) -> bool:
    """Check if the model is an OpenAI reasoning model with n<=8 limits."""
    return any(model.startswith(prefix) for prefix in ["o", "gpt-5"])


def normalize_vertex_model_name(model: str) -> str:
    """Normalize Gemini model names for Vertex AI OpenAI-compatible requests.

    Args:
        model: Model name provided by the caller.

    Returns:
        Vertex-compatible model name, with publisher prefix when required.
    """
    if is_gemini_model(model) and "/" not in model:
        return f"google/{model}"
    return model


def max_n_for_model(model: str) -> int | None:
    """Return max supported n for the model, or None if no known cap."""
    if is_gemini_model(model):
        return 5
    if is_reasoning_model(model):
        return 8
    return None


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


def get_openai_client_for_model(model: str, api_key: str | None = None) -> Any:
    """Create an OpenAI-compatible client for the given model."""
    if is_gemini_model(model):
        return OpenAICredentialsRefresher(
            api_key=api_key, base_url=get_vertex_openai_base_url()
        )
    return OpenAI(api_key=api_key) if api_key else OpenAI()


def query_llm(
    messages: List[Dict[str, str]],
    n_samples: int,
    model: str = "gpt-4o",
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    response_format=None,
    client: Any = None,
    debug_requests: bool = False,
):
    if client is None:
        client = get_openai_client_for_model(model)
    is_gemini = is_gemini_model(model)
    is_reasoning = is_reasoning_model(model)
    model_name = normalize_vertex_model_name(model) if is_gemini else model

    max_n = max_n_for_model(model)
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
        if temperature is not None and not is_reasoning:
            kwargs["temperature"] = temperature

        if is_reasoning and reasoning_effort is not None:
            kwargs["reasoning_effort"] = reasoning_effort

        try:
            if response_format is not None:
                response = client.beta.chat.completions.parse(
                    **kwargs, response_format=response_format
                )
            else:
                response = client.chat.completions.create(**kwargs)
        except ValidationError:
            # Retry if the response format validation fails
            response = client.beta.chat.completions.parse(**kwargs, response_format=response_format)
        return response

    responses = []
    if len(batch_sizes) == 1:
        response = _call_llm(batch_sizes[0])
        response_list = [response]
    elif is_gemini:
        max_workers = min(8, len(batch_sizes))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_call_llm, batch_n) for batch_n in batch_sizes]
            response_list = [future.result() for future in futures]
    else:
        response_list = [_call_llm(batch_n) for batch_n in batch_sizes]

    for response in response_list:
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
    """
    Fuse n independent Gaussian beliefs N(mu_i, sigma_i^2)
    into a single Gaussian via product of Gaussians.

    Parameters
    ----------
    means : array-like, shape (n,)
        The means μ_i of the Gaussian beliefs.
    stds : array-like, shape (n,)
        The standard deviations σ_i of the Gaussian beliefs.
    weight : float, optional
        A weight to apply to the precision of each Gaussian. Default is 1.0.

    Returns
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


def fetch_from_s3(links: List[str], download_dir="_s3") -> List[str]:
    """
    Download data from S3 URLs
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
