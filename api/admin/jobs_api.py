"""Admin API for managing autodiscovery jobs."""

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import BadRequest

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
    # Note: autodiscovery_jobs package not available
    # Logging deferred to when application context exists


def create() -> Blueprint:
    """Create the admin jobs API blueprint."""
    api = Blueprint("admin_jobs_api", __name__)

    def get_job_manager() -> JobManager:
        """Get a configured JobManager instance."""
        if not JOBS_AVAILABLE:
            raise RuntimeError("autodiscovery_jobs package not available")

        # Get config from environment or use defaults
        config = JobConfig.from_env()
        return JobManager(config)

    @api.route("/health")
    def health():
        """Health check endpoint."""
        if not JOBS_AVAILABLE:
            current_app.logger.warning(
                "autodiscovery_jobs package not available - job management features disabled"
            )
        return jsonify({"status": "ok", "jobs_available": JOBS_AVAILABLE})

    @api.route("/list/<userid>")
    def list_jobs(userid: str):
        """List all jobs for a user."""
        try:
            manager = get_job_manager()
            jobs = manager.list_jobs(userid)
            return jsonify({"jobs": jobs})
        except Exception as e:
            current_app.logger.error(f"Failed to list jobs: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/create", methods=["POST"])
    def create_job():
        """Create a new job."""
        data = request.json
        if not data:
            raise BadRequest("No request body")

        userid = data.get("userid")
        jobid = data.get("jobid")

        if not userid or not jobid:
            raise BadRequest("userid and jobid are required")

        try:
            manager = get_job_manager()
            path = manager.create_job(userid, jobid)
            return jsonify({"path": path, "message": "Job created successfully"})
        except JobAlreadyExistsError as e:
            return jsonify({"error": str(e)}), 409
        except Exception as e:
            current_app.logger.error(f"Failed to create job: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/exists/<userid>/<jobid>")
    def job_exists(userid: str, jobid: str):
        """Check if a job exists."""
        try:
            manager = get_job_manager()
            exists = manager.job_exists(userid, jobid)
            return jsonify({"exists": exists})
        except Exception as e:
            current_app.logger.error(f"Failed to check job existence: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/delete", methods=["POST"])
    def delete_job():
        """Delete a job."""
        data = request.json
        if not data:
            raise BadRequest("No request body")

        userid = data.get("userid")
        jobid = data.get("jobid")

        if not userid or not jobid:
            raise BadRequest("userid and jobid are required")

        try:
            manager = get_job_manager()
            manager.delete_job(userid, jobid)
            return jsonify({"message": "Job deleted successfully"})
        except JobNotFoundError as e:
            return jsonify({"error": str(e)}), 404
        except Exception as e:
            current_app.logger.error(f"Failed to delete job: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/upload-dataset", methods=["POST"])
    def upload_dataset():
        """Upload a dataset file for a job."""
        # Check if file is in request
        if "file" not in request.files:
            raise BadRequest("No file provided")

        file = request.files["file"]
        if file.filename == "":
            raise BadRequest("No file selected")

        userid = request.form.get("userid")
        jobid = request.form.get("jobid")

        if not userid or not jobid:
            raise BadRequest("userid and jobid are required")

        try:
            manager = get_job_manager()

            # Save file temporarily
            import os
            import tempfile
            from pathlib import Path

            with tempfile.NamedTemporaryFile(
                delete=False, suffix=Path(file.filename).suffix
            ) as tmp:
                file.save(tmp.name)
                tmp_path = Path(tmp.name)

            try:
                # Upload to GCS with original filename
                path = manager.upload_dataset(userid, jobid, tmp_path, remote_name=file.filename)
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

    @api.route("/upload-metadata", methods=["POST"])
    def upload_metadata():
        """Upload metadata for a job."""
        data = request.json
        if not data:
            raise BadRequest("No request body")

        userid = data.get("userid")
        jobid = data.get("jobid")
        metadata = data.get("metadata")

        if not userid or not jobid or not metadata:
            raise BadRequest("userid, jobid, and metadata are required")

        try:
            manager = get_job_manager()
            path = manager.upload_metadata(userid, jobid, metadata)
            return jsonify({"path": path, "message": "Metadata uploaded successfully"})
        except Exception as e:
            current_app.logger.error(f"Failed to upload metadata: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/run", methods=["POST"])
    def run_job():
        """Run a Cloud Run job."""
        data = request.json
        if not data:
            raise BadRequest("No request body")

        userid = data.get("userid")
        jobid = data.get("jobid")

        if not userid or not jobid:
            raise BadRequest("userid and jobid are required")

        # Extract job parameters
        n_experiments = data.get("n_experiments")
        model = data.get("model")

        if n_experiments is None:
            raise BadRequest("Number of Experiments is required")

        try:
            manager = get_job_manager()
            execution_id = manager.run_job(
                userid,
                jobid,
                n_experiments=n_experiments,
                model=model,
                **{
                    k: v
                    for k, v in data.items()
                    if k not in ["userid", "jobid", "n_experiments", "model"]
                },
            )
            return jsonify({"execution_id": execution_id, "message": "Job started successfully"})
        except Exception as e:
            current_app.logger.error(f"Failed to run job: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/status/<execution_id>")
    def get_status(execution_id: str):
        """Get job execution status."""
        try:
            manager = get_job_manager()
            status = manager.get_job_status(execution_id)
            return jsonify(status)
        except Exception as e:
            current_app.logger.error(f"Failed to get job status: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/logs/<execution_id>")
    def get_logs(execution_id: str):
        """Get job logs."""
        limit = request.args.get("limit", default=50, type=int)

        try:
            manager = get_job_manager()
            logs = manager.get_job_logs(execution_id, limit=limit)
            return jsonify({"logs": logs})
        except Exception as e:
            current_app.logger.error(f"Failed to get job logs: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/cancel", methods=["POST"])
    def cancel_job():
        """Cancel a running job."""
        data = request.json
        if not data:
            raise BadRequest("No request body")

        execution_id = data.get("execution_id")

        if not execution_id:
            raise BadRequest("execution_id is required")

        try:
            manager = get_job_manager()
            manager.cancel_job(execution_id)
            return jsonify({"message": "Job cancelled successfully"})
        except Exception as e:
            current_app.logger.error(f"Failed to cancel job: {e}")
            return jsonify({"error": str(e)}), 500

    return api
