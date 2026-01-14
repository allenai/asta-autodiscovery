"""Tests for Cloud Run operations."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from autodiscovery_jobs import cloudrun
from autodiscovery_jobs.exceptions import CloudRunError


def test_run_job_basic(mock_config):
    """Test basic job execution."""
    with patch("autodiscovery_jobs.cloudrun.run_v2.JobsClient") as mock_jobs_client:
        # Mock the client and operation
        mock_client = Mock()
        mock_jobs_client.return_value = mock_client

        mock_operation = Mock()
        # Mock the metadata.name attribute that the code actually uses
        mock_operation.metadata.name = "projects/test-project/locations/us-west1/jobs/test-job/executions/test-job-abc123"
        mock_client.run_job.return_value = mock_operation

        execution_id = cloudrun.run_job(
            "testuser", "job1", mock_config, n_experiments=4, model="gpt-4o"
        )

        assert execution_id == "test-job-abc123"
        mock_client.run_job.assert_called_once()

        # Check that request was constructed correctly
        call_args = mock_client.run_job.call_args
        request = call_args[1]["request"]
        assert "test-project" in request.name
        assert len(request.overrides.container_overrides) > 0
        args = request.overrides.container_overrides[0].args
        assert any("--n_experiments=4" in arg for arg in args)
        assert any("--model=gpt-4o" in arg for arg in args)


def test_run_job_with_optional_params(mock_config):
    """Test job execution with optional parameters."""
    with patch("autodiscovery_jobs.cloudrun.run_v2.JobsClient") as mock_jobs_client:
        mock_client = Mock()
        mock_jobs_client.return_value = mock_client

        mock_operation = Mock()
        # Mock the metadata.name attribute that the code actually uses
        mock_operation.metadata.name = "projects/test-project/locations/us-west1/jobs/test-job/executions/test-job-xyz"
        mock_client.run_job.return_value = mock_operation

        execution_id = cloudrun.run_job(
            "testuser",
            "job1",
            mock_config,
            n_experiments=8,
            model="gpt-4o",
            belief_model="gpt-4o",
            temperature=1.0,
            k_experiments=8,
            mcts_selection="ucb1_recursive",
        )

        # Check that optional parameters were included
        call_args = mock_client.run_job.call_args
        request = call_args[1]["request"]
        args = request.overrides.container_overrides[0].args

        assert any("--belief_model=gpt-4o" in arg for arg in args)
        assert any("--temperature=1.0" in arg for arg in args)
        assert any("--k_experiments=8" in arg for arg in args)
        assert any("--mcts_selection=ucb1_recursive" in arg for arg in args)


def test_run_job_failure(mock_config):
    """Test job execution failure."""
    with patch("autodiscovery_jobs.cloudrun.run_v2.JobsClient") as mock_jobs_client:
        mock_client = Mock()
        mock_jobs_client.return_value = mock_client
        mock_client.run_job.side_effect = Exception("API Error")

        with pytest.raises(CloudRunError):
            cloudrun.run_job("testuser", "job1", mock_config, n_experiments=4, model="gpt-4o")


def test_get_job_status(mock_config):
    """Test getting job status."""
    with patch("autodiscovery_jobs.cloudrun.run_v2.ExecutionsClient") as mock_executions_client:
        mock_client = Mock()
        mock_executions_client.return_value = mock_client

        mock_execution = Mock()
        mock_execution.name = "projects/test-project/locations/us-west1/jobs/test-job/executions/test-execution"
        mock_execution.uid = "abc-123"
        mock_execution.create_time = None
        mock_execution.start_time = None
        mock_execution.completion_time = None
        mock_execution.running_count = 0
        mock_execution.succeeded_count = 1
        mock_execution.failed_count = 0
        mock_execution.cancelled_count = 0
        mock_execution.reconciling = False
        mock_execution.conditions = []

        mock_client.get_execution.return_value = mock_execution

        status = cloudrun.get_job_status("test-execution", mock_config)

        assert status["phase"] == "SUCCEEDED"
        assert status["uid"] == "abc-123"
        assert status["succeeded_count"] == 1


def test_get_job_status_failure(mock_config):
    """Test getting job status failure."""
    with patch("autodiscovery_jobs.cloudrun.run_v2.ExecutionsClient") as mock_executions_client:
        mock_client = Mock()
        mock_executions_client.return_value = mock_client
        mock_client.get_execution.side_effect = Exception("Not found")

        with pytest.raises(CloudRunError):
            cloudrun.get_job_status("nonexistent", mock_config)


def test_cancel_job(mock_config):
    """Test canceling a job."""
    with patch("autodiscovery_jobs.cloudrun.run_v2.ExecutionsClient") as mock_executions_client:
        mock_client = Mock()
        mock_executions_client.return_value = mock_client

        mock_operation = Mock()
        mock_operation.result.return_value = None
        mock_client.cancel_execution.return_value = mock_operation

        cloudrun.cancel_job("test-execution", mock_config)

        mock_client.cancel_execution.assert_called_once()
        call_args = mock_client.cancel_execution.call_args
        request = call_args[1]["request"]
        assert "test-execution" in request.name


def test_get_job_logs(mock_config):
    """Test getting job logs."""
    with patch("autodiscovery_jobs.cloudrun.cloud_logging.Client") as mock_logging_client:
        mock_client = Mock()
        mock_logging_client.return_value = mock_client

        # Create mock log entries
        mock_entry1 = Mock()
        mock_entry1.payload = "Log line 1"

        mock_entry2 = Mock()
        mock_entry2.payload = "Log line 2"

        mock_entry3 = Mock()
        mock_entry3.payload = {"message": "Structured log"}

        mock_client.list_entries.return_value = [mock_entry1, mock_entry2, mock_entry3]

        logs = cloudrun.get_job_logs("test-execution", mock_config, limit=50)

        # Should return both text and dict payloads
        assert len(logs) == 3
        assert logs[0] == "Log line 1"
        assert logs[1] == "Log line 2"
        assert "message" in logs[2]


def test_get_job_logs_no_execution_id(mock_config):
    """Test getting logs without execution ID filter."""
    with patch("autodiscovery_jobs.cloudrun.cloud_logging.Client") as mock_logging_client:
        mock_client = Mock()
        mock_logging_client.return_value = mock_client
        mock_client.list_entries.return_value = []

        logs = cloudrun.get_job_logs(None, mock_config, limit=50)

        assert logs == []

        # Check that filter doesn't include execution_name
        call_args = mock_client.list_entries.call_args
        filter_str = call_args[1]["filter_"]
        assert "execution_name" not in filter_str
