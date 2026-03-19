"""Tests for JobManager class."""

from unittest.mock import patch

from autodiscovery_jobs import JobManager


def test_manager_initialization(mock_config):
    """Test JobManager initialization."""
    manager = JobManager(mock_config)
    assert manager.config == mock_config


def test_manager_default_config():
    """Test JobManager with default config."""
    manager = JobManager()
    assert manager.config is not None
    assert manager.config.bucket == "autodiscovery"


def test_get_user_path(mock_config):
    """Test get_user_path method."""
    manager = JobManager(mock_config)
    path = manager.get_user_path("testuser")
    assert "testuser" in path


def test_list_jobs(mock_config):
    """Test list_jobs method."""
    with patch("autodiscovery_jobs.gcs.list_user_jobs") as mock_list:
        mock_list.return_value = ["job1", "job2"]

        manager = JobManager(mock_config)
        jobs = manager.list_jobs("testuser")

        assert jobs == ["job1", "job2"]
        mock_list.assert_called_once_with("testuser", mock_config)


def test_job_exists(mock_config):
    """Test job_exists method."""
    with patch("autodiscovery_jobs.gcs.job_exists") as mock_exists:
        mock_exists.return_value = True

        manager = JobManager(mock_config)
        exists = manager.job_exists("testuser", "job1")

        assert exists is True
        mock_exists.assert_called_once_with("testuser", "job1", mock_config)


def test_create_job(mock_config):
    """Test create_job method."""
    with patch("autodiscovery_jobs.gcs.create_job_directory") as mock_create:
        mock_create.return_value = "gs://test-bucket/users/testuser/jobs/job1/"

        manager = JobManager(mock_config)
        path = manager.create_job("testuser", "job1")

        assert "job1" in path
        mock_create.assert_called_once_with("testuser", "job1", mock_config, False)


def test_delete_job(mock_config):
    """Test delete_job method."""
    with patch("autodiscovery_jobs.gcs.delete_job_directory") as mock_delete:
        manager = JobManager(mock_config)
        manager.delete_job("testuser", "job1")

        mock_delete.assert_called_once_with("testuser", "job1", mock_config)


def test_upload_dataset(mock_config, tmp_path):
    """Test upload_dataset method."""
    test_file = tmp_path / "data.csv"
    test_file.write_text("col1,col2\n1,2")

    with patch("autodiscovery_jobs.gcs.upload_dataset") as mock_upload:
        mock_upload.return_value = "gs://test-bucket/users/testuser/jobs/job1/data/"

        manager = JobManager(mock_config)
        path = manager.upload_dataset("testuser", "job1", test_file)

        assert "data/" in path
        mock_upload.assert_called_once()


def test_upload_metadata(mock_config):
    """Test upload_metadata method."""
    metadata = {"datasets": [{"name": "test.csv"}]}

    with patch("autodiscovery_jobs.gcs.upload_metadata") as mock_upload:
        mock_upload.return_value = "gs://test-bucket/users/testuser/jobs/job1/metadata.json"

        manager = JobManager(mock_config)
        path = manager.upload_metadata("testuser", "job1", metadata)

        assert "metadata.json" in path
        mock_upload.assert_called_once_with("testuser", "job1", metadata, mock_config)


def test_get_shared_run_owner_success(mock_config):
    """Test get_shared_run_owner returns userid when run is shared."""
    with patch("autodiscovery_jobs.gcs.get_userid_for_job") as mock_get_userid, \
         patch("autodiscovery_jobs.gcs.get_metadata") as mock_get_metadata:
        # Mock finding the owner
        mock_get_userid.return_value = "testuser"

        # Mock metadata with is_shared=True
        mock_get_metadata.return_value = {"is_shared": True, "name": "Test Run"}

        manager = JobManager(mock_config)
        userid = manager.get_shared_run_owner("shared-run-123")

        assert userid == "testuser"
        mock_get_userid.assert_called_once_with("shared-run-123", mock_config)
        mock_get_metadata.assert_called_once_with("testuser", "shared-run-123", mock_config)


def test_get_shared_run_owner_not_shared(mock_config):
    """Test get_shared_run_owner returns None when run is not shared."""
    with patch("autodiscovery_jobs.gcs.get_userid_for_job") as mock_get_userid, \
         patch("autodiscovery_jobs.gcs.get_metadata") as mock_get_metadata:
        # Mock finding the owner
        mock_get_userid.return_value = "testuser"

        # Mock metadata with is_shared=False
        mock_get_metadata.return_value = {"is_shared": False, "name": "Private Run"}

        manager = JobManager(mock_config)
        userid = manager.get_shared_run_owner("private-run-456")

        assert userid is None
        mock_get_userid.assert_called_once()
        mock_get_metadata.assert_called_once()


def test_get_shared_run_owner_not_found(mock_config):
    """Test get_shared_run_owner returns None when run doesn't exist."""
    with patch("autodiscovery_jobs.gcs.get_userid_for_job") as mock_get_userid:
        # Mock run not found
        mock_get_userid.return_value = None

        manager = JobManager(mock_config)
        userid = manager.get_shared_run_owner("nonexistent-run-789")

        assert userid is None
        mock_get_userid.assert_called_once_with("nonexistent-run-789", mock_config)


def test_get_shared_run_owner_metadata_missing_is_shared(mock_config):
    """Test get_shared_run_owner returns None when metadata lacks is_shared."""
    with patch("autodiscovery_jobs.gcs.get_userid_for_job") as mock_get_userid, \
         patch("autodiscovery_jobs.gcs.get_metadata") as mock_get_metadata:
        # Mock finding the owner
        mock_get_userid.return_value = "testuser"

        # Mock metadata without is_shared field
        mock_get_metadata.return_value = {"name": "Old Run"}

        manager = JobManager(mock_config)
        userid = manager.get_shared_run_owner("old-run-000")

        assert userid is None


def test_get_shared_run_owner_metadata_error(mock_config):
    """Test get_shared_run_owner returns None when metadata read fails."""
    with patch("autodiscovery_jobs.gcs.get_userid_for_job") as mock_get_userid, \
         patch("autodiscovery_jobs.gcs.get_metadata") as mock_get_metadata:
        # Mock finding the owner
        mock_get_userid.return_value = "testuser"

        # Mock metadata read failing
        mock_get_metadata.side_effect = Exception("GCS error")

        manager = JobManager(mock_config)
        userid = manager.get_shared_run_owner("error-run-999")

        # Should return None on error (safe default)
        assert userid is None


def test_run_job(mock_config):
    """Test run_job method."""
    with patch("autodiscovery_jobs.cloudrun.run_job") as mock_run:
        mock_run.return_value = "execution-123"

        manager = JobManager(mock_config)
        execution_id = manager.run_job(
            "testuser", "job1", n_experiments=4, model="gpt-4o", temperature=1.0
        )

        assert execution_id == "execution-123"
        mock_run.assert_called_once()


def test_get_job_status(mock_config):
    """Test get_job_status method."""
    with patch("autodiscovery_jobs.cloudrun.get_job_status") as mock_status:
        mock_status.return_value = {"status": {"phase": "SUCCEEDED"}}

        manager = JobManager(mock_config)
        status = manager.get_job_status("execution-123")

        assert status["status"]["phase"] == "SUCCEEDED"
        mock_status.assert_called_once_with("execution-123", mock_config)


def test_cancel_job(mock_config):
    """Test cancel_job method."""
    with patch("autodiscovery_jobs.cloudrun.cancel_job") as mock_cancel:
        manager = JobManager(mock_config)
        manager.cancel_job("execution-123")

        mock_cancel.assert_called_once_with("execution-123", mock_config)


def test_get_job_logs(mock_config):
    """Test get_job_logs method."""
    with patch("autodiscovery_jobs.cloudrun.get_job_logs") as mock_logs:
        mock_logs.return_value = ["log1", "log2", "log3"]

        manager = JobManager(mock_config)
        logs = manager.get_job_logs("execution-123", limit=100)

        assert len(logs) == 3
        mock_logs.assert_called_once_with("execution-123", mock_config, 100)


def test_get_results(mock_config):
    """Test get_results method."""
    with patch("autodiscovery_jobs.gcs.get_job_results") as mock_results:
        mock_results.return_value = [
            "gs://test-bucket/users/testuser/jobs/job1/output/result1.json",
            "gs://test-bucket/users/testuser/jobs/job1/output/result2.csv",
        ]

        manager = JobManager(mock_config)
        results = manager.get_results("testuser", "job1")

        assert len(results) == 2
        mock_results.assert_called_once_with("testuser", "job1", mock_config)


def test_download_results(mock_config, tmp_path):
    """Test download_results method."""
    local_dir = tmp_path / "results"

    with patch("autodiscovery_jobs.gcs.download_job_results") as mock_download:
        mock_download.return_value = [
            local_dir / "result1.json",
            local_dir / "result2.csv",
        ]

        manager = JobManager(mock_config)
        paths = manager.download_results("testuser", "job1", local_dir)

        assert len(paths) == 2
        mock_download.assert_called_once_with("testuser", "job1", local_dir, mock_config)


def test_setup_and_run(mock_config, tmp_path):
    """Test setup_and_run convenience method."""
    test_file = tmp_path / "data.csv"
    test_file.write_text("col1,col2\n1,2")
    metadata = {"datasets": [{"name": "data.csv"}]}

    with (
        patch("autodiscovery_jobs.gcs.create_job_directory") as mock_create,
        patch("autodiscovery_jobs.gcs.upload_dataset") as mock_upload_data,
        patch("autodiscovery_jobs.gcs.upload_metadata") as mock_upload_meta,
        patch("autodiscovery_jobs.cloudrun.run_job") as mock_run,
    ):
        mock_create.return_value = "gs://test-bucket/users/testuser/jobs/job1/"
        mock_upload_data.return_value = "gs://test-bucket/users/testuser/jobs/job1/data/"
        mock_upload_meta.return_value = "gs://test-bucket/users/testuser/jobs/job1/metadata.json"
        mock_run.return_value = "execution-123"

        manager = JobManager(mock_config)
        execution_id = manager.setup_and_run(
            "testuser", "job1", test_file, metadata, n_experiments=4, model="gpt-4o"
        )

        assert execution_id == "execution-123"

        # Verify all steps were called
        mock_create.assert_called_once()
        mock_upload_data.assert_called_once()
        mock_upload_meta.assert_called_once()
        mock_run.assert_called_once()
