"""Pytest fixtures for autodiscovery_jobs tests."""

import pytest
from unittest.mock import Mock, MagicMock
from autodiscovery_jobs.config import JobConfig


@pytest.fixture
def mock_config():
    """Create a test configuration."""
    return JobConfig(
        bucket="test-bucket",
        project_id="test-project",
        region="us-west1",
        job_name="test-job",
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
    """Mock google.cloud.storage.Client."""
    client, bucket = mock_gcs_client

    def mock_client(*args, **kwargs):
        return client

    monkeypatch.setattr("autodiscovery_jobs.gcs.storage.Client", mock_client)
    return client, bucket
