"""Tests for GCS operations."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from autodiscovery_jobs import gcs
from autodiscovery_jobs.exceptions import GCSError, JobNotFoundError, JobAlreadyExistsError


def test_parse_gcs_path():
    """Test GCS path parsing."""
    # With gs:// prefix
    bucket, prefix = gcs.parse_gcs_path("gs://my-bucket/path/to/data")
    assert bucket == "my-bucket"
    assert prefix == "path/to/data/"

    # Without gs:// prefix
    bucket, prefix = gcs.parse_gcs_path("my-bucket/path/to/data/")
    assert bucket == "my-bucket"
    assert prefix == "path/to/data/"

    # Just bucket
    bucket, prefix = gcs.parse_gcs_path("gs://my-bucket")
    assert bucket == "my-bucket"
    assert prefix == ""


def test_get_user_path(mock_config):
    """Test user path construction."""
    path = gcs.get_user_path("testuser", mock_config)
    assert path == "gs://test-bucket/users/testuser/"


def test_get_job_path(mock_config):
    """Test job path construction."""
    path = gcs.get_job_path("testuser", "job1", mock_config)
    assert path == "gs://test-bucket/users/testuser/jobs/job1/"


def test_list_user_jobs(mock_config, mock_storage_client):
    """Test listing user jobs."""
    client, bucket = mock_storage_client

    # Mock list_blobs to return an iterable with prefixes
    blobs_mock = MagicMock()
    blobs_mock.__iter__.return_value = iter([])  # Make it iterable (empty list)
    blobs_mock.prefixes = [
        "users/testuser/jobs/job1/",
        "users/testuser/jobs/job2/",
        "users/testuser/jobs/job3/",
    ]
    bucket.list_blobs.return_value = blobs_mock

    jobs = gcs.list_user_jobs("testuser", mock_config)

    assert jobs == ["job1", "job2", "job3"]
    bucket.list_blobs.assert_called_once()


def test_job_exists(mock_config, mock_storage_client):
    """Test checking if job exists."""
    client, bucket = mock_storage_client

    # Job exists
    blobs = [Mock()]
    bucket.list_blobs.return_value = iter(blobs)
    assert gcs.job_exists("testuser", "job1", mock_config) is True

    # Job doesn't exist
    bucket.list_blobs.return_value = iter([])
    assert gcs.job_exists("testuser", "job2", mock_config) is False


def test_create_job_directory(mock_config, mock_storage_client):
    """Test creating job directory."""
    client, bucket = mock_storage_client

    # Mock job_exists to return False
    with patch("autodiscovery_jobs.gcs.job_exists", return_value=False):
        blob_mock = Mock()
        bucket.blob.return_value = blob_mock

        path = gcs.create_job_directory("testuser", "newjob", mock_config)

        assert path == "gs://test-bucket/users/testuser/jobs/newjob/"
        # Should create placeholders for data/ and output/
        assert bucket.blob.call_count == 2
        assert blob_mock.upload_from_string.call_count == 2


def test_create_job_directory_already_exists(mock_config, mock_storage_client):
    """Test error when creating existing job."""
    with patch("autodiscovery_jobs.gcs.job_exists", return_value=True):
        with pytest.raises(JobAlreadyExistsError):
            gcs.create_job_directory("testuser", "existingjob", mock_config)


def test_delete_job_directory(mock_config, mock_storage_client):
    """Test deleting job directory."""
    client, bucket = mock_storage_client

    # Mock job_exists to return True
    with patch("autodiscovery_jobs.gcs.job_exists", return_value=True):
        # Mock blobs to delete
        blob1, blob2 = Mock(), Mock()
        bucket.list_blobs.return_value = iter([blob1, blob2])

        gcs.delete_job_directory("testuser", "job1", mock_config)

        blob1.delete.assert_called_once()
        blob2.delete.assert_called_once()


def test_delete_job_directory_not_found(mock_config, mock_storage_client):
    """Test error when deleting non-existent job."""
    with patch("autodiscovery_jobs.gcs.job_exists", return_value=False):
        with pytest.raises(JobNotFoundError):
            gcs.delete_job_directory("testuser", "nonexistent", mock_config)


def test_upload_dataset_file(mock_config, mock_storage_client, tmp_path):
    """Test uploading single dataset file."""
    client, bucket = mock_storage_client

    # Create test file
    test_file = tmp_path / "data.csv"
    test_file.write_text("col1,col2\n1,2")

    with patch("autodiscovery_jobs.gcs.job_exists", return_value=True):
        blob_mock = Mock()
        bucket.blob.return_value = blob_mock

        path = gcs.upload_dataset("testuser", "job1", test_file, mock_config)

        assert "data/" in path
        blob_mock.upload_from_filename.assert_called_once()


def test_upload_metadata(mock_config, mock_storage_client):
    """Test uploading metadata."""
    client, bucket = mock_storage_client

    metadata = {"datasets": [{"name": "test.csv"}]}

    with patch("autodiscovery_jobs.gcs.job_exists", return_value=True):
        blob_mock = Mock()
        bucket.blob.return_value = blob_mock

        path = gcs.upload_metadata("testuser", "job1", metadata, mock_config)

        assert "metadata.json" in path
        blob_mock.upload_from_string.assert_called_once()


def test_get_job_results(mock_config, mock_storage_client):
    """Test listing job results."""
    client, bucket = mock_storage_client

    with patch("autodiscovery_jobs.gcs.job_exists", return_value=True):
        # Mock result blobs
        blob1 = Mock()
        blob1.name = "users/testuser/jobs/job1/output/result1.json"
        blob2 = Mock()
        blob2.name = "users/testuser/jobs/job1/output/result2.csv"
        blob3 = Mock()
        blob3.name = "users/testuser/jobs/job1/output/.placeholder"

        bucket.list_blobs.return_value = iter([blob1, blob2, blob3])

        results = gcs.get_job_results("testuser", "job1", mock_config)

        # Should return 2 results (not placeholder)
        assert len(results) == 2
        assert any("result1.json" in r for r in results)
        assert any("result2.csv" in r for r in results)


def test_download_job_results(mock_config, mock_storage_client, tmp_path):
    """Test downloading job results."""
    client, bucket = mock_storage_client

    with patch("autodiscovery_jobs.gcs.job_exists", return_value=True):
        # Mock result blobs
        blob1 = Mock()
        blob1.name = "users/testuser/jobs/job1/output/result.json"

        bucket.list_blobs.return_value = iter([blob1])

        local_dir = tmp_path / "results"
        paths = gcs.download_job_results("testuser", "job1", local_dir, mock_config)

        assert len(paths) == 1
        assert local_dir in paths[0].parents
        blob1.download_to_filename.assert_called_once()
