"""User-facing API for managing autodiscovery runs.

This module provides authenticated endpoints for users to create and manage
their own autodiscovery experiment runs.
"""

import json
import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from google.cloud import storage
from utils.auth import requires_enrollment
from utils.credits import InsufficientCreditsError, check_sufficient_credits, get_job_stats
from utils.experiments import ExperimentTree
from werkzeug.exceptions import BadRequest

from runs.models import (
    MetadataModel,
    GetRunMetadataRequestModel,
    GetRunMetadataResponseModel,
    RunDetailsModel,
    RunModel,
    ExperimentModel,
    GetExperimentStatusResponseModel,
    GetRunExperimentsResponseModel,
    GetViewerRunsRequestModel,
    GetViewerRunsResponseModel,
    RunStatsModel,
    RunArgsModel,
    GenerateUploadUrlRequestModel,
    GenerateUploadUrlResponseModel,
)

# Import autodiscovery_jobs when available
try:
    from autodiscovery_jobs import JobConfig, JobManager
    from autodiscovery_jobs.exceptions import (
        CloudRunError,
        GCSError,
        JobAlreadyExistsError,
        JobNotFoundError,
    )
    from autodiscovery_jobs.gcs import read_rich_outputs

    JOBS_AVAILABLE = True
except ImportError:
    JOBS_AVAILABLE = False

# Trigger phrase in intent field that activates simulated run mode
SIMULATE_RUN_TRIGGER = "%asta.simulate_run%"

# Max size of files that can be uploaded
UPLOAD_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 * 1024  # 50GB

# Allowed file extensions for uploads
UPLOAD_ALLOWED_EXTENSIONS = {".csv", ".json", ".txt", ".tsv"}

# Expiration time for presigned upload URLs
UPLOAD_URL_EXPIRATION_SECONDS = 3600  # 1 hour

# Users whose runs are publicly accessible (can be queried by anyone)
PUBLIC_USERS = {"samples"}


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

    def _get_run_detail_with_updated_status(
        run_details: dict, userid: str, runid: str
    ) -> tuple[dict, dict] | None:
        """Update run details with the job status from Cloud Run.

        Args:
            run_details: Current run details dictionary
            userid: User ID
            runid: Run ID

        Returns:
            Tuple of updated run details with status and the status response itself
        """
        manager = get_job_manager()
        if run_details.get("execution_id"):
            execution_id = run_details["execution_id"]

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
            return run_details, status_response

        return run_details, None

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

    def _get_userid_for_read(allow_public: bool = True) -> tuple[str | None, tuple | None]:
        """Get the user ID to use for read operations.

        Checks for a 'userid' query parameter. If provided and the user is in PUBLIC_USERS,
        returns that user ID. Otherwise, returns the authenticated user's ID.

        Args:
            allow_public: Whether to allow public user access (default True)

        Returns:
            Tuple of (userid, error_response). If error_response is not None,
            it should be returned directly from the endpoint.
        """
        userid_param = request.args.get("userid")
        if userid_param:
            if not allow_public or userid_param not in PUBLIC_USERS:
                return None, (
                    jsonify(
                        {"error": f"Access denied. Cannot query runs for userid: {userid_param}"}
                    ),
                    403,
                )
            return userid_param, None

        userid = request.user.get("sub")
        if not userid:
            return None, (jsonify({"error": "User ID not found in token"}), 401)
        return userid, None

    @api.route("/list", methods=["GET"])
    @requires_enrollment
    def list_runs():
        """List runs for a user.

        Query Parameters:
            userid: Optional user ID to query. If not provided, uses the authenticated user.
                  Only users in PUBLIC_USERS can be queried by others.
            limit: Maximum number of runs to return (default: 1000)

        Returns:
            JSON response containing run metadata, details, and stats.
        """
        userid, error = _get_userid_for_read()
        if error:
            return error

        req = GetViewerRunsRequestModel(
            limit=int(request.args.get("limit", 1000)),
            userid=userid,
        )

        job_manager = get_job_manager()
        run_ids = job_manager.list_jobs(req.userid)

        # TODO the order at this point is meaningless (UUID-sorted) so truncating before
        # fetching details will be confusing. FIXME
        sliced_run_ids = run_ids[: req.limit]
        run_models: list[RunModel] = []
        app_logger = current_app.logger

        def _build_run_model(run_id: str) -> RunModel | None:
            # Parallelize I/O-heavy GCS calls to reduce tail latency.
            try:
                run_details = _get_run_details(req.userid, run_id) or {}
            except Exception as e:
                app_logger.error(f"Failed to get run details for {run_id}: {e}")
                run_details = {}
            try:
                job_stats = get_job_stats(
                    userid=req.userid, jobid=run_id, config=job_manager.config
                )
            except Exception as e:
                app_logger.error(f"Failed to get job stats for {run_id}: {e}")
                job_stats = None
            try:
                metadata_dict = job_manager.get_metadata(req.userid, run_id)
            except Exception as e:
                app_logger.error(f"Failed to get metadata for {run_id}: {e}")
                metadata_dict = None

            run_details_model = RunDetailsModel(
                execution_id=run_details.get("execution_id"),
                created_at=run_details.get("created_at", ""),
                status=run_details.get("status", "UNKNOWN"),
                status_checked_at=run_details.get("status_checked_at"),
            )
            run_stats_model = RunStatsModel(
                requested_experiments=job_stats.num_experiments_requested if job_stats else 0,
                completed_experiments=job_stats.num_experiments_completed if job_stats else 0,
                pending_experiments=job_stats.num_experiments_pending if job_stats else 0,
                num_surprising_experiments=0,  # TODO: Update when surprising experiments are tracked
            )
            run_metadata_model = MetadataModel.from_dict(metadata_dict) if metadata_dict else None
            return RunModel(
                runid=run_id,
                userid=req.userid,
                status=run_details.get("status", "UNKNOWN"),
                name=run_metadata_model.name if run_metadata_model else f"Run {run_id}",
                description=run_metadata_model.description
                if run_metadata_model
                else f"Description for Run {run_id}",
                path=None,
                run_args=None,
                run_stats=run_stats_model,
                run_details=run_details_model,
                run_metadata=run_metadata_model,
                execution_status={},
            )

        if sliced_run_ids:
            from concurrent.futures import ThreadPoolExecutor

            max_workers = min(8, len(sliced_run_ids))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                run_models = [
                    model for model in executor.map(_build_run_model, sliced_run_ids) if model
                ]

        # Sort by created_at descending (newest first)
        run_models.sort(
            key=lambda r: r.run_details.created_at if r.run_details else "",
            reverse=True,
        )

        resp = GetViewerRunsResponseModel(
            runs=run_models,
        )
        return jsonify(resp.model_dump()), 200

    @api.route("/<runid>")
    @requires_enrollment
    def get_run(runid: str):
        """Get details for a specific run.

        Args:
            runid: Run identifier.

        Query Parameters:
            userid: Optional user ID to query. Only users in PUBLIC_USERS can be queried by others.

        Returns:
            JSON response with run details as RunModel.
        """
        userid, error = _get_userid_for_read()
        if error:
            return error

        try:
            manager = get_job_manager()
            exists = manager.job_exists(userid, runid)

            if not exists:
                return jsonify({"error": "Run not found"}), 404

            # Get run details
            run_details = _get_run_details(userid, runid) or {}
            path = manager.get_job_path(userid, runid)

            # Get the latest run status
            try:
                [updated_run_details, _] = _get_run_detail_with_updated_status(
                    run_details, userid, runid
                )
            except Exception as e:
                current_app.logger.error(f"Failed to update run status for {runid}: {e}")
                updated_run_details = run_details

            # Get job stats
            try:
                job_stats = get_job_stats(userid=userid, jobid=runid, config=manager.config)
            except Exception as e:
                current_app.logger.error(f"Failed to get job stats for {runid}: {e}")
                job_stats = None

            # Get metadata
            try:
                metadata_dict = manager.get_metadata(userid, runid)
            except Exception as e:
                current_app.logger.error(f"Failed to get metadata for {runid}: {e}")
                metadata_dict = None

            # Get args
            try:
                args_dict = manager.get_job_args(userid, runid)
            except Exception as e:
                current_app.logger.error(f"Failed to get job args for {runid}: {e}")
                args_dict = None

            # Build RunModel
            run_details_model = RunDetailsModel(
                execution_id=updated_run_details.get("execution_id"),
                created_at=updated_run_details.get("created_at", ""),
                status=updated_run_details.get("status", "UNKNOWN"),
                status_checked_at=updated_run_details.get("status_checked_at"),
            )
            run_stats_model = RunStatsModel(
                requested_experiments=job_stats.num_experiments_requested if job_stats else 0,
                completed_experiments=job_stats.num_experiments_completed if job_stats else 0,
                pending_experiments=job_stats.num_experiments_pending if job_stats else 0,
                num_surprising_experiments=0,  # TODO: Update when surprising experiments are tracked
            )
            run_metadata_model = MetadataModel.from_dict(metadata_dict) if metadata_dict else None
            run_args_model = RunArgsModel.from_dict(args_dict) if args_dict else None
            run_model = RunModel(
                runid=runid,
                userid=userid,
                status=updated_run_details.get("status", "UNKNOWN"),
                name=run_metadata_model.name if run_metadata_model else f"Run {runid}",
                description=run_metadata_model.description if run_metadata_model else None,
                path=path,
                run_stats=run_stats_model,
                run_details=run_details_model,
                run_metadata=run_metadata_model,
                run_args=run_args_model,
                execution_status={},
            )

            return jsonify(run_model.model_dump()), 200

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

    @api.route("/<runid>/generate-upload-url", methods=["POST"])
    @requires_enrollment
    def generate_upload_url(runid: str):
        """Generate a presigned URL for direct GCS upload.

        This endpoint creates a signed URL that allows the browser to upload
        files directly to GCS without routing through the Flask server.

        Args:
            runid: Run identifier (from URL path)

        Request body:
            filename: Name of file to upload
            content_type: MIME type of file
            file_size_bytes: Size of file in bytes

        Returns:
            JSON with upload_url, gcs_path, filename, and expires_at_unix (Unix timestamp)

        Raises:
            BadRequest: If required fields are missing or validation fails
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        data = request.get_json()
        if not data:
            raise BadRequest("No request body")

        # Parse and validate request using Pydantic model
        try:
            req = GenerateUploadUrlRequestModel(runid=runid, userid=userid, **data)
        except Exception as e:
            raise BadRequest(f"Invalid request body: {e}")

        try:
            # Validate file size
            if req.file_size_bytes < 0:
                return jsonify({"error": "Invalid file size."}), 400
            if req.file_size_bytes > UPLOAD_MAX_FILE_SIZE_BYTES:
                return jsonify({"error": "File too large."}), 413

            # Validate file extension
            file_ext = Path(req.filename).suffix.lower()
            if file_ext not in UPLOAD_ALLOWED_EXTENSIONS:
                return jsonify({"error": f"File type not allowed: {file_ext}"}), 400

            manager = get_job_manager()

            # Generate presigned URL using gcs module
            result = manager.generate_upload_url(
                userid=req.userid,
                jobid=req.runid,
                filename=req.filename,
                content_type=req.content_type,
                expiration_seconds=UPLOAD_URL_EXPIRATION_SECONDS,
            )

            # Calculate expiration timestamp
            expires_at = datetime.now(UTC) + timedelta(seconds=UPLOAD_URL_EXPIRATION_SECONDS)
            expires_at_unix = int(expires_at.timestamp())

            # Return response using Pydantic model
            resp = GenerateUploadUrlResponseModel(
                upload_url=result["upload_url"],
                gcs_path=result["gcs_path"],
                filename=req.filename,
                expires_at_unix=expires_at_unix,
            )
            return jsonify(resp.model_dump()), 200

        except JobNotFoundError as e:
            return jsonify({"error": str(e)}), 404
        except GCSError as e:
            current_app.logger.error(f"Failed to generate upload URL: {e}")
            return jsonify({"error": str(e)}), 400
        except Exception as e:
            current_app.logger.error(f"Failed to generate upload URL: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<runid>/metadata", methods=["POST"])
    @requires_enrollment
    def save_metadata(runid: str):
        """Save or update metadata for a run.

        Args:
            runid: Run identifier from URL path

        Expects JSON body with:
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

        metadata = data.get("metadata")

        if not metadata:
            raise BadRequest("metadata is required")

        try:
            manager = get_job_manager()
            path = manager.upload_metadata(userid, runid, metadata)
            return jsonify({"path": path, "message": "Metadata saved successfully"})
        except Exception as e:
            current_app.logger.error(f"Failed to save metadata: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<runid>/args", methods=["POST"])
    @requires_enrollment
    def save_job_args(runid: str):
        """Save or update job arguments for a run.

        Args:
            runid: Run identifier from URL path

        Expects JSON body with:
        - args: Job arguments object

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

        args = data.get("args")

        if not args:
            raise BadRequest("args is required")

        try:
            manager = get_job_manager()
            path = manager.upload_job_args(userid, runid, args)
            return jsonify({"path": path, "message": "Job args saved successfully"})
        except Exception as e:
            current_app.logger.error(f"Failed to save job args: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("<runid>/metadata", methods=["GET"])
    @requires_enrollment
    def get_run_metadata(runid: str):
        """Fetch metadata for a specific run.

        Args:
            runid: Run identifier

        Query Parameters:
            userid: Optional user ID to query. Only users in PUBLIC_USERS can be queried by others.
        """
        userid, error = _get_userid_for_read()
        if error:
            return error

        req = GetRunMetadataRequestModel(
            runid=runid,
            userid=userid,
        )

        job_manager = get_job_manager()
        metadata_dict = job_manager.get_metadata(req.userid, req.runid)
        if not metadata_dict:
            return jsonify({"error": "Metadata not found"}), 404

        metadata_model = MetadataModel.from_dict(metadata_dict)

        resp = GetRunMetadataResponseModel(
            runid=req.runid,
            metadata=metadata_model,
        )
        return jsonify(resp.model_dump()), 200

    @api.route("/submit", methods=["POST"])
    @requires_enrollment
    def submit_run():
        """Submit a run for execution.

        Expects JSON body with:
        - runid: Run identifier
        - n_experiments: Number of experiments
        - model: Model name (optional, uses args.py default when omitted)
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
        n_experiments = data.get("n_experiments")
        model = data.get("model")
        belief_model = data.get("belief_model")

        try:
            manager = get_job_manager()

            # Check if this is a simulated run (replay mode)
            intent = data.get("intent", "")
            is_simulated = SIMULATE_RUN_TRIGGER in intent

            if is_simulated:
                # Run replay job instead of actual AutoDiscovery job
                current_app.logger.info(f"Running replay job for {userid}/{runid}")

                from utils.dev import run_simulated_job

                execution_id = run_simulated_job(
                    userid=userid,
                    jobid=runid,
                    bucket=manager.config.bucket,
                    project_id=manager.config.project_id,
                    region=manager.config.region,
                )
            else:
                if n_experiments is None:
                    raise BadRequest("Number of Experiments is required")

                # Validate sufficient credits before submission
                check_sufficient_credits(
                    n_experiments=n_experiments, userid=userid, config=manager.config
                )

                # Pass all additional parameters to run_job
                execution_id = manager.run_job(
                    userid,
                    runid,
                    # Remap UI parameters to equivalent AutoDiscovery name
                    user_query=intent,
                    **{
                        k: v
                        for k, v in data.items()
                        # Exclude parameters that are meaningless to AutoDiscovery job
                        if k not in ["runid", "intent"]
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

        except InsufficientCreditsError as e:
            return jsonify(
                {"error": e.message, "requested": e.requested, "available": e.available}
            ), 402  # Payment Required

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

        Query Parameters:
            userid: Optional user ID to query. Only users in PUBLIC_USERS can be queried by others.

        Returns:
            JSON response with run status details
        """
        userid, error = _get_userid_for_read()
        if error:
            return error

        try:
            # Get run details
            run_details = _get_run_details(userid, runid)
            if not run_details:
                return jsonify({"error": "Run details not found"}), 404

            [updated_run_details, status_response] = _get_run_detail_with_updated_status(
                run_details, userid, runid
            )

            if status_response:
                return jsonify(
                    {
                        "runid": runid,
                        "run_details": updated_run_details,
                        "execution_status": status_response,
                    }
                )
            else:
                # Run hasn't been submitted yet
                return jsonify(
                    {
                        "runid": runid,
                        "run_details": run_details,
                    }
                )
        except Exception as e:
            current_app.logger.error(f"Failed to get run status: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<runid>/experiments", methods=["GET"])
    @requires_enrollment
    def get_run_experiments(runid: str):
        """Fetch details about the experiments within a run. This is used to build
        the experiments table in the UI.

        Args:
            runid: Run identifier

        Query Parameters:
            after_experiment_id: Node ID after which to fetch experiments (for smaller payloads when polling)
            userid: Optional user ID to query. Only users in PUBLIC_USERS can be queried by others.
        """
        userid, error = _get_userid_for_read()
        if error:
            return error
        after_experiment_id = request.args.get("after_experiment_id", None)

        # Get job status to determine if polling can stop
        job_manager = get_job_manager()
        run_details = _get_run_details(userid, runid) or {}
        has_job_completed = run_details.get("status") in ["SUCCEEDED", "FAILED", "CANCELLED"]

        # Load experiment tree and convert to models
        tree = ExperimentTree.load(userid=userid, jobid=runid, config=job_manager.config)
        experiment_nodes = tree.to_experiment_models(after_experiment_id=after_experiment_id)
        experiment_models = [ExperimentModel(**node) for node in experiment_nodes]

        resp = GetRunExperimentsResponseModel(
            runid=runid,
            after_experiment_id=after_experiment_id,
            experiments=experiment_models,
            has_job_completed=has_job_completed,
        )
        return jsonify(resp.model_dump()), 200

    @api.route("/<runid>/experiments/<experiment_id>", methods=["GET"])
    @requires_enrollment
    def get_run_experiment_details(runid: str, experiment_id: str):
        """Fetch details about a specific experiment within a run.

        Query Parameters:
            userid: Optional user ID to query. Only users in PUBLIC_USERS can be queried by others.
        """
        userid, error = _get_userid_for_read()
        if error:
            return error

        job_manager = get_job_manager()
        tree = ExperimentTree.load(userid=userid, jobid=runid, config=job_manager.config)
        node = tree.get_node(experiment_id)

        experiment_node = node.to_dict() if node else None
        if experiment_node and node:
            experiment_node["code_output"] = node.code_output
            if node.level is not None and node.index is not None:
                try:
                    experiment_node["rich_outputs"] = read_rich_outputs(
                        userid,
                        runid,
                        node.level,
                        node.index,
                        config=job_manager.config,
                    )
                except Exception as e:
                    current_app.logger.warning(
                        "Failed to read rich outputs for %s: %s", experiment_id, e
                    )
                    experiment_node["rich_outputs"] = []
            else:
                experiment_node["rich_outputs"] = []
        experiment_model = ExperimentModel(**experiment_node) if experiment_node else None

        resp = GetExperimentStatusResponseModel(
            runid=runid,
            experiment_id=experiment_id,
            experiment=experiment_model,
        )
        return jsonify(resp.model_dump()), 200

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
