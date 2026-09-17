"""Pytest fixtures for autodiscovery_jobs tests."""

from unittest.mock import Mock

import pytest
from autodiscovery_jobs.config import JobConfig


@pytest.fixture
def mock_config():
    """Create a test configuration for the cloud path.

    Pins the Cloud Run job backend and the GCS store explicitly; both default to
    the local/docker pair, but most fixtures here exercise the GCP path. (The two
    must be pinned together: local storage plus Cloud Run jobs is rejected as
    unworkable — see ``manager._validate_storage_config``.)
    """
    return JobConfig(
        storage_backend="gcs",
        bucket="test-bucket",
        project_id="test-project",
        region="us-west1",
        job_name="test-job",
        backend="gcp",
    )


@pytest.fixture
def local_config(tmp_path):
    """Create a test configuration on the default local filesystem store.

    Backed by a real directory under ``tmp_path``, so tests exercise the store
    end to end rather than against mocks.
    """
    return JobConfig(
        storage_backend="local",
        storage_dir=str(tmp_path / "store"),
        job_name="test-job",
        backend="docker",
        job_image="autodiscovery:test",
    )


@pytest.fixture
def mock_gcs_client():
    """Create a mock GCS client."""
    client = Mock()
    bucket = Mock()
    client.bucket.return_value = bucket
    return client, bucket


@pytest.fixture
def mock_storage_client(monkeypatch, mock_gcs_client):
    """Mock google.cloud.storage.Client.

    ``GcsStore`` obtains its client via the shared, cached
    ``autodiscovery_jobs.client.get_storage_client`` factory, so patch the
    construction site there and clear the per-process cache so each test gets
    its own mock rather than a client cached by an earlier test.
    """
    import autodiscovery_jobs.client as client_module

    client, bucket = mock_gcs_client

    def mock_client(*args, **kwargs):
        return client

    client_module._clients.clear()
    monkeypatch.setattr("autodiscovery_jobs.client.storage.Client", mock_client)
    monkeypatch.setattr(client_module, "_clients", {})
    return client, bucket
