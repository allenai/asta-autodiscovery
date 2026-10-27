"""Ownership checks use metadata from the owner's artifact listing."""

from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("requests")

from asta import context_client  # noqa: E402


@pytest.mark.parametrize("wrapped", [False, True])
def test_find_owned_artifact_uses_nested_metadata(wrapped):
    metadata = {
        "artifact_id": "artifact-1",
        "path": "gs://example/owners/owner-1/context/input.csv",
    }
    entries = [
        {"metadata": None, "download_url": "https://data.example/untracked"},
        {"metadata": {"artifact_id": "artifact-2"}},
        {"metadata": metadata, "download_url": "https://data.example/input.csv"},
    ]
    response = MagicMock()
    response.json.return_value = (
        {"artifacts": entries, "continuation": None} if wrapped else entries
    )
    with (
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_URL", "https://context.example"),
        patch.object(context_client, "ASTA_CONTEXT_SERVICE_API_KEY", "key"),
        patch.object(context_client.requests, "get", return_value=response) as get,
    ):
        assert context_client.find_owned_artifact("owner-1", "artifact-1") == metadata
    get.assert_called_once_with(
        "https://context.example/api/owners/owner-1/artifacts",
        headers={"Authorization": "Bearer key"},
        timeout=30,
    )


def test_find_owned_artifact_rejects_missing_metadata_or_missing_id():
    with patch.object(
        context_client,
        "list_owner_artifacts",
        return_value=[
            {"id": "artifact-1", "metadata": None},
            {"metadata": {"artifact_id": "artifact-2"}},
        ],
    ):
        assert context_client.find_owned_artifact("owner-1", "artifact-1") is None
