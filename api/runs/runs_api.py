"""User-facing API for managing autodiscovery runs.

This module provides authenticated endpoints for users to create and manage
their own autodiscovery experiment runs.
"""

import json
import os
import tempfile
from urllib import response
import uuid
from datetime import UTC, datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from google.cloud import storage
from utils.auth import requires_enrollment
from utils.experiments import ExperimentTree
from werkzeug.exceptions import BadRequest

from runs.models import ExperimentModel, GetExperimentStatusResponseModel, GetRunExperimentsResponseModel

# Import autodiscovery_jobs when available
try:
    from autodiscovery_jobs import JobConfig, JobManager
    from autodiscovery_jobs.exceptions import (
        CloudRunError,
        GCSError,
        JobAlreadyExistsError,
        JobNotFoundError,
    )

    JOBS_AVAILABLE = True
except ImportError:
    JOBS_AVAILABLE = False


def create() -> Blueprint:
    """Create the runs API blueprint.

    Returns:
        Flask Blueprint with user run management endpoints.
    """
    api = Blueprint("runs_api", __name__)

    def get_job_manager() -> JobManager:
        """Get a configured JobManager instance.

        Returns:
            JobManager configured from environment variables.

        Raises:
            RuntimeError: If autodiscovery_jobs package is not available.
        """
        if not JOBS_AVAILABLE:
            raise RuntimeError("autodiscovery_jobs package not available")

        config = JobConfig.from_env()
        return JobManager(config)

    def _get_run_details_path(userid: str, runid: str) -> str:
        """Get the GCS path for run_details.json.

        Args:
            userid: User identifier
            runid: Run identifier

        Returns:
            Blob path for run_details.json
        """
        return f"users/{userid}/jobs/{runid}/run_details.json"

    def _create_run_details(userid: str, runid: str) -> dict:
        """Create initial run_details.json file.

        Args:
            userid: User identifier
            runid: Run identifier

        Returns:
            Run details dictionary
        """
        if not JOBS_AVAILABLE:
            raise RuntimeError("autodiscovery_jobs package not available")

        config = JobConfig.from_env()
        client = storage.Client(project=config.project_id)
        bucket = client.bucket(config.bucket)

        run_details = {
            "execution_id": None,
            "created_at": datetime.now(UTC).isoformat(),
            "status": "CREATED",
            "status_checked_at": None,
        }

        blob_path = _get_run_details_path(userid, runid)
        blob = bucket.blob(blob_path)
        blob.upload_from_string(json.dumps(run_details, indent=2))

        return run_details

    def _get_run_details(userid: str, runid: str) -> dict | None:
        """Get run details from GCS.

        Args:
            userid: User identifier
            runid: Run identifier

        Returns:
            Run details dictionary or None if not found
        """
        if not JOBS_AVAILABLE:
            raise RuntimeError("autodiscovery_jobs package not available")

        config = JobConfig.from_env()
        client = storage.Client(project=config.project_id)
        bucket = client.bucket(config.bucket)

        blob_path = _get_run_details_path(userid, runid)
        blob = bucket.blob(blob_path)

        try:
            if blob.exists():
                content = blob.download_as_text()
                return json.loads(content)
        except Exception as e:
            current_app.logger.error(f"Failed to get run details: {e}")

        return None

    def _update_run_details(userid: str, runid: str, updates: dict) -> dict:
        """Update run details in GCS.

        Args:
            userid: User identifier
            runid: Run identifier
            updates: Dictionary of fields to update

        Returns:
            Updated run details dictionary
        """
        if not JOBS_AVAILABLE:
            raise RuntimeError("autodiscovery_jobs package not available")

        config = JobConfig.from_env()
        client = storage.Client(project=config.project_id)
        bucket = client.bucket(config.bucket)

        # Get existing details
        run_details = _get_run_details(userid, runid)
        if not run_details:
            run_details = {
                "execution_id": None,
                "created_at": datetime.now(UTC).isoformat(),
                "status": "CREATED",
                "status_checked_at": None,
            }

        # Update fields
        run_details.update(updates)

        # Save back to GCS
        blob_path = _get_run_details_path(userid, runid)
        blob = bucket.blob(blob_path)
        blob.upload_from_string(json.dumps(run_details, indent=2))

        return run_details

    @api.route("/health")
    def health():
        """Health check endpoint.

        Returns:
            JSON response with health status and jobs availability.
        """
        if not JOBS_AVAILABLE:
            current_app.logger.warning(
                "autodiscovery_jobs package not available - run management features disabled"
            )
        return jsonify({"status": "ok", "jobs_available": JOBS_AVAILABLE})

    @api.route("/create", methods=["POST"])
    @requires_enrollment
    def create_run():
        """Create a new run with auto-generated UUID.

        Extracts user ID from authenticated JWT token and creates a new
        run directory in GCS with a unique identifier.

        Returns:
            JSON response with runid and GCS path.

        Raises:
            BadRequest: If request body is missing or invalid.
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        # Generate unique run ID
        runid = str(uuid.uuid4())

        try:
            manager = get_job_manager()
            path = manager.create_job(userid, runid)

            # Create run_details.json
            run_details = _create_run_details(userid, runid)

            return jsonify(
                {
                    "runid": runid,
                    "path": path,
                    "message": "Run created successfully",
                    "run_details": run_details,
                }
            )
        except JobAlreadyExistsError as e:
            # This should be extremely rare with UUIDs
            return jsonify({"error": str(e)}), 409
        except Exception as e:
            current_app.logger.error(f"Failed to create run: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/list")
    @requires_enrollment
    def list_runs():
        """List all runs for the authenticated user.

        Returns:
            JSON response with array of run IDs.
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        try:
            manager = get_job_manager()
            runs = manager.list_jobs(userid)
            return jsonify({"runs": runs})
        except Exception as e:
            current_app.logger.error(f"Failed to list runs: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<runid>")
    @requires_enrollment
    def get_run(runid: str):
        """Get details for a specific run.

        Args:
            runid: Run identifier.

        Returns:
            JSON response with run details.
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        try:
            manager = get_job_manager()
            exists = manager.job_exists(userid, runid)

            if not exists:
                return jsonify({"error": "Run not found"}), 404

            # Get run details
            run_details = _get_run_details(userid, runid)
            path = manager.get_job_path(userid, runid)

            return jsonify(
                {
                    "runid": runid,
                    "path": path,
                    "userid": userid,
                    "run_details": run_details,
                }
            )
        except Exception as e:
            current_app.logger.error(f"Failed to get run details: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<runid>", methods=["DELETE"])
    @requires_enrollment
    def delete_run(runid: str):
        """Delete a run and all its contents.

        Args:
            runid: Run identifier.

        Returns:
            JSON response confirming deletion.
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        try:
            manager = get_job_manager()
            manager.delete_job(userid, runid)
            return jsonify({"message": "Run deleted successfully"})
        except JobNotFoundError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            current_app.logger.error(f"Failed to delete run: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/upload-dataset", methods=["POST"])
    @requires_enrollment
    def upload_dataset():
        """Upload a dataset file for a run.

        Expects multipart/form-data with:
        - file: Dataset file
        - runid: Run identifier

        Returns:
            JSON response with upload confirmation and file details.

        Raises:
            BadRequest: If file or runid is missing.
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        # Check if file is in request
        if "file" not in request.files:
            raise BadRequest("No file provided")

        file = request.files["file"]
        if file.filename == "":
            raise BadRequest("No file selected")

        runid = request.form.get("runid")
        if not runid:
            raise BadRequest("runid is required")

        try:
            manager = get_job_manager()

            # Save file temporarily
            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(file.filename).suffix
            ) as tmp:
                file.save(tmp.name)
                tmp_path = Path(tmp.name)

            try:
                # Upload to GCS with original filename
                path = manager.upload_dataset(userid, runid, tmp_path, remote_name=file.filename)
                return jsonify(
                    {
                        "path": path,
                        "filename": file.filename,
                        "message": "Dataset uploaded successfully",
                    }
                )
            finally:
                # Clean up temp file
                if tmp_path.exists():
                    os.unlink(tmp_path)

        except Exception as e:
            current_app.logger.error(f"Failed to upload dataset: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/metadata", methods=["POST"])
    @requires_enrollment
    def save_metadata():
        """Save or update metadata for a run.

        Expects JSON body with:
        - runid: Run identifier
        - metadata: Metadata object (typically with "datasets" array)

        Returns:
            JSON response with upload confirmation.

        Raises:
            BadRequest: If request body is missing or invalid.
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        data = request.json
        if not data:
            raise BadRequest("No request body")

        runid = data.get("runid")
        metadata = data.get("metadata")

        if not runid or not metadata:
            raise BadRequest("runid and metadata are required")

        try:
            manager = get_job_manager()
            path = manager.upload_metadata(userid, runid, metadata)
            return jsonify({"path": path, "message": "Metadata saved successfully"})
        except Exception as e:
            current_app.logger.error(f"Failed to save metadata: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/submit", methods=["POST"])
    @requires_enrollment
    def submit_run():
        """Submit a run for execution.

        Expects JSON body with:
        - runid: Run identifier
        - n_experiments: Number of experiments (optional, default: 4)
        - model: Model name (optional, default: "gpt-4o")
        - belief_model: Belief model (optional)
        - Additional optional parameters

        Returns:
            JSON response with execution ID.

        Raises:
            BadRequest: If request body is missing or invalid.
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        data = request.json
        if not data:
            raise BadRequest("No request body")

        runid = data.get("runid")
        if not runid:
            raise BadRequest("runid is required")

        # Extract run parameters
        n_experiments = data.get("n_experiments", 4)
        model = data.get("model", "gpt-4o")
        belief_model = data.get("belief_model")

        try:
            manager = get_job_manager()

            # Pass all additional parameters to run_job
            execution_id = manager.run_job(
                userid,
                runid,
                n_experiments=n_experiments,
                model=model,
                belief_model=belief_model,
                **{
                    k: v
                    for k, v in data.items()
                    if k not in ["runid", "n_experiments", "model", "belief_model"]
                },
            )

            # Update run_details.json with execution_id and status
            _update_run_details(
                userid,
                runid,
                {
                    "execution_id": execution_id,
                    "status": "RUNNING",
                    "status_checked_at": datetime.now(UTC).isoformat(),
                },
            )

            return jsonify({"execution_id": execution_id, "message": "Run submitted successfully"})
        except Exception as e:
            current_app.logger.error(f"Failed to submit run: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<runid>/status")
    @requires_enrollment
    def get_run_status(runid: str):
        """Get the current status of a run.

        Checks the Cloud Run execution status and updates run_details.json.

        Args:
            runid: Run identifier

        Returns:
            JSON response with run status details
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        try:
            manager = get_job_manager()

            # Get run details
            run_details = _get_run_details(userid, runid)
            if not run_details:
                return jsonify({"error": "Run details not found"}), 404

            # If run has been submitted, check execution status
            if run_details.get("execution_id"):
                execution_id = run_details["execution_id"]

                try:
                    # Get status from Cloud Run
                    status_response = manager.get_job_status(execution_id)

                    # Extract phase from execution status (e.g., "RUNNING", "SUCCEEDED", "FAILED")
                    phase = status_response.get("phase", status_response.get("status", "unknown"))

                    # Update run_details with new status
                    run_details = _update_run_details(
                        userid,
                        runid,
                        {
                            "status": phase,
                            "status_checked_at": datetime.now(UTC).isoformat(),
                        },
                    )

                    return jsonify(
                        {
                            "runid": runid,
                            "run_details": run_details,
                            "execution_status": status_response,
                        }
                    )
                except Exception as e:
                    current_app.logger.error(f"Failed to get execution status: {e}")
                    # Return current run_details even if status check fails
                    return jsonify(
                        {
                            "runid": runid,
                            "run_details": run_details,
                            "error": f"Failed to check execution status: {str(e)}",
                        }
                    )

            # Run hasn't been submitted yet
            return jsonify({"runid": runid, "run_details": run_details})

        except Exception as e:
            current_app.logger.error(f"Failed to get run status: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<runid>/experiments/status", methods=["GET"])
    @requires_enrollment
    def get_experiments_status(runid: str, after_experiment_id: str | None = None):
        """Fetch details about the experiments within a run. This is used to build
        the experiments table in the UI.

        Args:
            runid: Run identifier
            after_experiment_id: Node ID after which to fetch experiments (for smaller payloads when polling)
        """
        userid = request.user.get("sub")

        try:
            tree = ExperimentTree.load(userid, runid)
            experiments = tree.to_experiment_models(after_experiment_id=after_experiment_id)

            resp = GetRunExperimentsResponseModel(
                run_id=runid,
                after_experiment_id=after_experiment_id,
                experiments=experiments,
            )
            return jsonify(resp.model_dump())
        except Exception as e:
            current_app.logger.error(f"Failed to load experiments for run {runid}: {e}")
            # Return empty list on error to gracefully handle missing/incomplete runs
            resp = GetRunExperimentsResponseModel(
                run_id=runid,
                after_experiment_id=after_experiment_id,
                experiments=[],
            )
            return jsonify(resp.model_dump())

    @api.route("/<runid>/experiments/<experiment_id>", methods=["GET"])
    @requires_enrollment
    def get_experiment_details(runid: str, experiment_id: str):
        """Fetch details about a specific experiment within a run."""
        userid = request.user.get("sub")

        try:
            tree = ExperimentTree.load(userid, runid)
            node = tree.get_node(experiment_id)

            experiment = node.to_experiment_model() if node else None

            resp = GetExperimentStatusResponseModel(
                run_id=runid,
                experiment_id=experiment_id,
                experiment=experiment,
            )
            return jsonify(resp.model_dump())
        except Exception as e:
            current_app.logger.error(f"Failed to load experiment {experiment_id} for run {runid}: {e}")
            resp = GetExperimentStatusResponseModel(
                run_id=runid,
                experiment_id=experiment_id,
                experiment=None,
            )
            return jsonify(resp.model_dump())

    @api.route("/<runid>/cancel", methods=["POST"])
    @requires_enrollment
    def cancel_run(runid: str):
        """Cancel a running job.

        Args:
            runid: Run identifier

        Returns:
            JSON response confirming cancellation
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        try:
            manager = get_job_manager()

            # Get run details
            run_details = _get_run_details(userid, runid)
            if not run_details:
                return jsonify({"error": "Run details not found"}), 404

            execution_id = run_details.get("execution_id")
            if not execution_id:
                return jsonify({"error": "Run has not been submitted yet"}), 400

            # Cancel the job
            manager.cancel_job(execution_id)

            # Update run_details
            _update_run_details(
                userid,
                runid,
                {
                    "status": "CANCELLED",
                    "status_checked_at": datetime.now(UTC).isoformat(),
                },
            )

            return jsonify({"message": "Run cancelled successfully"})

        except Exception as e:
            current_app.logger.error(f"Failed to cancel run: {e}")
            return jsonify({"error": str(e)}), 500

    return api
