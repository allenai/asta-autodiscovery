"""User-facing API for managing autodiscovery runs.

This module provides authenticated endpoints for users to create and manage
their own autodiscovery experiment runs.
"""

import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from utils.auth import (
    PermissionType,
    optional_enrollment,
    requires_auth,
    requires_enrollment,
)
from utils.credits import (
    ExperimentLimitExceededError,
    InsufficientCreditsError,
    InvalidExperimentCountError,
    check_experiment_limits,
    get_job_stats,
)
from utils.experiments import ExperimentTree
from werkzeug.exceptions import BadRequest

from runs.models import (
    BookmarkExperimentRequestModel,
    BookmarkExperimentResponseModel,
    BookmarkRunRequestModel,
    BookmarkRunResponseModel,
    CancelRunRequestModel,
    CancelRunResponseModel,
    CreateRunResponseModel,
    DeleteRunRequestModel,
    DeleteRunResponseModel,
    ExperimentModel,
    GenerateUploadUrlRequestModel,
    GenerateUploadUrlResponseModel,
    GetExperimentStatusResponseModel,
    GetRunExperimentsRequestModel,
    GetRunExperimentsResponseModel,
    GetRunMetadataRequestModel,
    GetRunMetadataResponseModel,
    GetRunRequestModel,
    GetRunStatusRequestModel,
    GetRunStatusResponseModel,
    GetViewerRunsRequestModel,
    GetViewerRunsResponseModel,
    MetadataModel,
    RunDetailsModel,
    RunModel,
    RunStatsModel,
    SaveMetadataRequestModel,
    SaveMetadataResponseModel,
    ShareRunRequestModel,
    ShareRunResponseModel,
    GetSharedRunOwnerRequestModel,
    GetSharedRunOwnerResponseModel,
    SubmitRunRequestModel,
    SubmitRunResponseModel,
    UploadDatasetResponseModel,
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
    from autodiscovery_jobs.run_details import (
        RunDetails,
        create_run_details,
        get_run_details,
        refresh_run_status,
        update_run_details,
    )

    JOBS_AVAILABLE = True
except ImportError:
    JOBS_AVAILABLE = False

# Trigger phrase in intent field that activates simulated run mode
SIMULATE_RUN_TRIGGER = "%asta.simulate_run%"

# Max size of files that can be uploaded
UPLOAD_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 * 1024  # 50GB default
UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_BYTES = 100 * 1024 * 1024 * 1024  # 100GB for users with higher upload limit permission
UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_STR = "100GB"

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
    @requires_auth(check_permissions=[PermissionType.HIGHER_UPLOAD_LIMIT])
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
            run_details = create_run_details(userid, runid)

            # Check if user has HIGHER_UPLOAD_LIMIT permission and return the actual limit
            has_higher_upload_limit = getattr(request, PermissionType.HIGHER_UPLOAD_LIMIT.value, False)
            max_file_size = UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_STR if has_higher_upload_limit else None

            resp = CreateRunResponseModel(
                runid=runid,
                path=path,
                message="Run created successfully",
                run_details=RunDetailsModel(**run_details.to_dict()),
                max_file_size=max_file_size,
            )
            return jsonify(resp.model_dump()), 200
        except JobAlreadyExistsError as e:
            # This should be extremely rare with UUIDs
            return jsonify({"error": str(e)}), 409
        except Exception as e:
            current_app.logger.error(f"Failed to create run: {e}")
            return jsonify({"error": str(e)}), 500

    def _get_userid_for_read() -> tuple[str | None, tuple | None]:
        """Get the authenticated user's ID from JWT token.

        Returns None with no error for unauthenticated users (when using optional_enrollment).

        Returns:
            Tuple of (userid, error_response). userid may be None for unauthenticated users.
        """
        userid = request.user.get("sub")
        return userid, None

    def _can_read_run(token_userid: str | None, userid: str, runid: str) -> bool:
        """Check if the requesting user can read the given run.

        Access is granted if:
        1. The requesting user owns the run, OR
        2. The run owner is in PUBLIC_USERS, OR
        3. The run is marked as shared (is_shared=True in metadata.json)
        """
        if token_userid and userid == token_userid:
            return True
        if userid in PUBLIC_USERS:
            return True
        # Check if the run is shared
        try:
            manager = get_job_manager()
            metadata = manager.get_metadata(userid, runid)
            if metadata and metadata.get("is_shared"):
                return True
        except Exception:
            pass
        return False

    def _check_run_not_deleted(userid: str, runid: str) -> tuple[None, None] | tuple[dict, int]:
        """Check if a run is deleted and return 404 error if so.

        Returns:
            Tuple of (None, None) if run is not deleted, or (error_response, status_code) if deleted.
        """
        try:
            run_details = get_run_details(userid, runid)
            if run_details and run_details.status == "DELETED":
                return jsonify({"error": "Run has been deleted"}), 404
        except Exception:
            # If we can't get run details, let the endpoint handle it
            pass
        return None, None

    @api.route("/<userid>/list", methods=["GET"])
    @optional_enrollment
    def list_runs(userid: str):
        """List runs for a specific user.

        Args:
            userid: User ID from URL path. Must match authenticated user or be in PUBLIC_USERS.

        Query Parameters:
            limit: Maximum number of runs to return (default: 1000)

        Returns:
            JSON response containing run metadata, details, and stats.
        """
        token_userid, error = _get_userid_for_read()
        if error:
            return error

        # Validate access: either viewing own data or viewing public user
        if userid != token_userid and userid not in PUBLIC_USERS:
            return jsonify({"error": "User cannot view other user's data"}), 403

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

        # Check if user has HIGHER_UPLOAD_LIMIT permission
        permissions = request.user.get("permissions", [])
        has_higher_upload_limit = PermissionType.HIGHER_UPLOAD_LIMIT.value in permissions
        max_file_size = UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_STR if has_higher_upload_limit else None

        def _build_run_model(run_id: str) -> RunModel | None:
            # Parallelize I/O-heavy GCS calls to reduce tail latency.
            try:
                run_details = get_run_details(req.userid, run_id)
            except Exception as e:
                app_logger.error(f"Failed to get run details for {run_id}: {e}")
                run_details = None

            # Skip DELETED runs from the list
            if run_details and run_details.status == "DELETED":
                return None

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
                execution_id=run_details.execution_id if run_details else None,
                created_at=run_details.created_at if run_details else "",
                status=run_details.status if run_details else "UNKNOWN",
                status_checked_at=run_details.status_checked_at if run_details else None,
                finished_at=run_details.finished_at_raw if run_details else None,
            )
            run_stats_model = RunStatsModel(
                requested_experiments=job_stats.num_experiments_requested,
                completed_experiments=job_stats.num_experiments_completed,
                pending_experiments=job_stats.num_experiments_pending,
                num_surprising_experiments=0,  # TODO: Update when surprising experiments are tracked
            ) if job_stats else None
            run_metadata_model = MetadataModel.from_dict(metadata_dict) if metadata_dict else None
            return RunModel(
                runid=run_id,
                userid=req.userid,
                status=run_details.status if run_details else "UNKNOWN",
                name=run_metadata_model.name if run_metadata_model else "Untitled draft",
                description=run_metadata_model.description
                if run_metadata_model
                else f"Description for Run {run_id}",
                path=None,
                run_stats=run_stats_model,
                run_details=run_details_model,
                run_metadata=run_metadata_model,
                execution_status={},
                max_file_size=max_file_size,
            )

        if sliced_run_ids:
            from concurrent.futures import ThreadPoolExecutor

            max_workers = min(8, len(sliced_run_ids))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                run_models = [
                    model for model in executor.map(_build_run_model, sliced_run_ids) if model
                ]

        # Sort by bookmark status (bookmarked first), then by most recent activity
        run_models.sort(
            key=lambda r: (
                # First sort key: bookmarked status (True > False with reverse=True)
                bool(r.run_metadata and r.run_metadata.is_bookmarked),
                # Second sort key: most recent activity (newer > older with reverse=True)
                r.run_details.status_checked_at or r.run_details.created_at if r.run_details else "",
            ),
            reverse=True,
        )

        resp = GetViewerRunsResponseModel(
            runs=run_models,
        )
        return jsonify(resp.model_dump()), 200

    @api.route("/<userid>/<runid>")
    @optional_enrollment
    def get_run(userid: str, runid: str):
        """Get details for a specific run.

        Args:
            userid: User ID from URL path. Must match authenticated user, be in PUBLIC_USERS,
                    or own a shared run.
            runid: Run identifier.

        Returns:
            JSON response with run details as RunModel.
        """
        token_userid, error = _get_userid_for_read()
        if error:
            return error

        if not _can_read_run(token_userid, userid, runid):
            return jsonify({"error": "User cannot view other user's data"}), 403

        req = GetRunRequestModel(runid=runid, userid=userid)

        try:
            manager = get_job_manager()
            exists = manager.job_exists(req.userid, req.runid)

            if not exists:
                return jsonify({"error": "Run not found"}), 404

            # Get run details with refreshed status from Cloud Run
            path = manager.get_job_path(req.userid, req.runid)

            try:
                run_details = refresh_run_status(req.userid, req.runid)
            except Exception as e:
                current_app.logger.error(f"Failed to refresh run status for {req.runid}: {e}")
                run_details = get_run_details(req.userid, req.runid)

            # Get job stats
            try:
                job_stats = get_job_stats(userid=req.userid, jobid=req.runid, config=manager.config)
            except Exception as e:
                current_app.logger.error(f"Failed to get job stats for {req.runid}: {e}")
                job_stats = None

            # Get metadata
            try:
                metadata_dict = manager.get_metadata(req.userid, req.runid)
            except Exception as e:
                current_app.logger.error(f"Failed to get metadata for {req.runid}: {e}")
                metadata_dict = None

            # Build RunModel
            run_details_model = RunDetailsModel(
                execution_id=run_details.execution_id if run_details else None,
                created_at=run_details.created_at if run_details else "",
                status=run_details.status if run_details else "UNKNOWN",
                status_checked_at=run_details.status_checked_at if run_details else None,
                finished_at=run_details.finished_at_raw if run_details else None,
            )
            run_stats_model = RunStatsModel(
                requested_experiments=job_stats.num_experiments_requested,
                completed_experiments=job_stats.num_experiments_completed,
                pending_experiments=job_stats.num_experiments_pending,
                num_surprising_experiments=0,  # TODO: Update when surprising experiments are tracked
            ) if job_stats else None
            run_metadata_model = MetadataModel.from_dict(metadata_dict) if metadata_dict else None

            # Check if user has HIGHER_UPLOAD_LIMIT permission
            permissions = request.user.get("permissions", [])
            has_higher_upload_limit = PermissionType.HIGHER_UPLOAD_LIMIT.value in permissions
            max_file_size = UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_STR if has_higher_upload_limit else None

            run_model = RunModel(
                runid=req.runid,
                userid=req.userid,
                status=run_details.status if run_details else "UNKNOWN",
                name=run_metadata_model.name if run_metadata_model else f"Run {req.runid}",
                description=run_metadata_model.description if run_metadata_model else None,
                path=path,
                run_stats=run_stats_model,
                run_details=run_details_model,
                run_metadata=run_metadata_model,
                execution_status={},
                max_file_size=max_file_size,
            )

            return jsonify(run_model.model_dump()), 200

        except Exception as e:
            current_app.logger.error(f"Failed to get run details: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<runid>", methods=["DELETE"])
    @requires_enrollment
    def delete_run(runid: str):
        """Soft delete a run - removes user data but preserves results.

        This endpoint performs a soft delete that:
        - Cancels the Cloud Run execution if job is running
        - Marks the run as DELETED in run_details.json
        - Deletes user-uploaded files in data/ directory (except .placeholder)
        - Preserves metadata.json, run_details.json, and all output/ files

        This operation is idempotent - calling it multiple times is safe.

        Args:
            runid: Run identifier.

        Returns:
            JSON response with deletion details including count of deleted/preserved files.
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        req = DeleteRunRequestModel(runid=runid, userid=userid)

        try:
            manager = get_job_manager()
            result = manager.soft_delete_job(req.userid, req.runid)

            resp = DeleteRunResponseModel(
                message="Run deleted successfully",
                deleted_files_count=len(result["deleted_files"]),
                preserved_files_count=result["preserved_files"],
                status=result["status"],
                deleted_at=result["deleted_at"],
                cancelled_execution=result.get("cancelled_execution", False),
            )
            return jsonify(resp.model_dump()), 200

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
                resp = UploadDatasetResponseModel(
                    path=path,
                    filename=file.filename,
                    message="Dataset uploaded successfully",
                )
                return jsonify(resp.model_dump()), 200
            finally:
                # Clean up temp file
                if tmp_path.exists():
                    os.unlink(tmp_path)

        except Exception as e:
            current_app.logger.error(f"Failed to upload dataset: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<runid>/generate-upload-url", methods=["POST"])
    @requires_auth(check_permissions=[PermissionType.HIGHER_UPLOAD_LIMIT])
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
            # Validate file size - use higher limit for users with permission
            has_higher_limit = getattr(request, PermissionType.HIGHER_UPLOAD_LIMIT.value, False)
            max_file_size = (
                UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_BYTES if has_higher_limit else UPLOAD_MAX_FILE_SIZE_BYTES
            )

            if req.file_size_bytes < 0:
                return jsonify({"error": "Invalid file size."}), 400
            if req.file_size_bytes > max_file_size:
                return jsonify({"error": "File too large."}), 413

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

        metadata_data = data.get("metadata")

        if not metadata_data:
            raise BadRequest("metadata is required")

        try:
            req = SaveMetadataRequestModel(
                runid=runid,
                userid=userid,
                metadata=MetadataModel.from_dict(metadata_data),
            )
        except Exception as e:
            raise BadRequest(f"Invalid request body: {e}")

        try:
            manager = get_job_manager()
            path = manager.upload_metadata(req.userid, req.runid, req.metadata.model_dump())
            resp = SaveMetadataResponseModel(
                path=path,
                message="Metadata saved successfully",
            )
            return jsonify(resp.model_dump()), 200
        except Exception as e:
            current_app.logger.error(f"Failed to save metadata: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("<userid>/<runid>/metadata", methods=["GET"])
    @optional_enrollment
    def get_run_metadata(userid: str, runid: str):
        """Fetch metadata for a specific run.

        Args:
            userid: User ID from URL path. Must match authenticated user, be in PUBLIC_USERS,
                    or own a shared run.
            runid: Run identifier
        """
        token_userid, error = _get_userid_for_read()
        if error:
            return error

        if not _can_read_run(token_userid, userid, runid):
            return jsonify({"error": "User cannot view other user's data"}), 403

        # Check if run is deleted
        error_response, status_code = _check_run_not_deleted(userid, runid)
        if error_response:
            return error_response, status_code

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

        Job configuration is read from the run's metadata.json file.

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

        runid_data = data.get("runid")
        if not runid_data:
            raise BadRequest("runid is required")

        req = SubmitRunRequestModel(runid=runid_data, userid=userid)

        try:
            manager = get_job_manager()

            # Read job configuration from metadata
            metadata = manager.get_metadata(req.userid, req.runid)
            if not metadata:
                raise BadRequest("Run metadata not found. Please save run configuration first.")

            intent = metadata.get("intent", "")
            n_experiments = metadata.get("n_experiments")

            # Check if this is a simulated run (replay mode)
            is_simulated = SIMULATE_RUN_TRIGGER in intent

            if is_simulated:
                # Run replay job instead of actual AutoDiscovery job
                current_app.logger.info(f"Running replay job for {req.userid}/{req.runid}")

                from utils.dev import run_simulated_job

                execution_id = run_simulated_job(
                    userid=req.userid,
                    jobid=req.runid,
                    bucket=manager.config.bucket,
                    project_id=manager.config.project_id,
                    region=manager.config.region,
                )
            else:
                if n_experiments is None:
                    raise BadRequest("Number of Experiments is required in metadata")

                # Validate experiment count and sufficient credits before submission
                check_experiment_limits(
                    n_experiments=n_experiments, userid=req.userid, config=manager.config
                )

                # Build job parameters from metadata
                job_params = {
                    "n_experiments": n_experiments,
                    "user_query": intent,
                }

                # Add optional parameters if present in metadata
                # Filter out None and empty strings, but allow 0 and other valid values
                optional_params = [
                    "exploration_weight",
                    "mcts_selection",
                    "surprisal_width",
                    "evidence_weight",
                    "warmstart_experiments",
                    "n_warmstart",
                ]
                for param in optional_params:
                    value = metadata.get(param)
                    if value is not None and value != "":
                        job_params[param] = value

                execution_id = manager.run_job(req.userid, req.runid, **job_params)

            # Capture origin URL for email links (e.g., localhost vs production)
            origin_url = request.headers.get("Origin")

            # Update run_details.json with execution_id and status
            update_run_details(
                req.userid,
                req.runid,
                {
                    "execution_id": execution_id,
                    "status": "RUNNING",
                    "status_checked_at": datetime.now(UTC).isoformat(),
                    "origin_url": origin_url,
                },
            )

            # Get updated run_details to return to frontend
            run_details = get_run_details(req.userid, req.runid)
            if not run_details:
                return jsonify({"error": "Failed to retrieve run details after submission"}), 500

            resp = SubmitRunResponseModel(
                execution_id=execution_id,
                message="Run submitted successfully",
                run_details=RunDetailsModel(**run_details.to_dict()),
            )
            return jsonify(resp.model_dump()), 200

        except InvalidExperimentCountError as e:
            return jsonify(
                {"error": e.message, "requested": e.requested}
            ), 400  # Bad Request

        except ExperimentLimitExceededError as e:
            return jsonify(
                {"error": e.message, "requested": e.requested, "limit": e.limit}
            ), 400  # Bad Request

        except InsufficientCreditsError as e:
            return jsonify(
                {"error": e.message, "requested": e.requested, "available": e.available}
            ), 402  # Payment Required

        except Exception as e:
            current_app.logger.error(f"Failed to submit run: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<userid>/<runid>/status")
    @optional_enrollment
    def get_run_status(userid: str, runid: str):
        """Get the current status of a run.

        Checks the Cloud Run execution status and updates run_details.json.

        Args:
            userid: User ID from URL path. Must match authenticated user, be in PUBLIC_USERS,
                    or own a shared run.
            runid: Run identifier

        Returns:
            JSON response with run status details
        """
        token_userid, error = _get_userid_for_read()
        if error:
            return error

        if not _can_read_run(token_userid, userid, runid):
            return jsonify({"error": "User cannot view other user's data"}), 403

        req = GetRunStatusRequestModel(runid=runid, userid=userid)

        try:
            # Get run details with refreshed status
            run_details = refresh_run_status(req.userid, req.runid)
            if not run_details:
                return jsonify({"error": "Run details not found"}), 404

            execution_status = None

            # If run has an execution_id, also fetch detailed Cloud Run status
            if run_details.execution_id:
                manager = get_job_manager()
                try:
                    execution_status = manager.get_job_status(run_details.execution_id)
                except Exception as e:
                    current_app.logger.warning(f"Failed to get execution status: {e}")

            resp = GetRunStatusResponseModel(
                runid=req.runid,
                run_details=RunDetailsModel(**run_details.to_dict()),
                execution_status=execution_status,
            )
            return jsonify(resp.model_dump()), 200
        except Exception as e:
            current_app.logger.error(f"Failed to get run status: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<userid>/<runid>/experiments", methods=["POST"])
    @optional_enrollment
    def get_run_experiments(userid: str, runid: str):
        """Fetch details about the experiments within a run. This is used to build
        the experiments table in the UI.

        Args:
            userid: User ID from URL path. Must match authenticated user, be in PUBLIC_USERS,
                    or own a shared run.
            runid: Run identifier

        Request Body:
            known_experiment_ids: List of experiment IDs the client already has
        """
        token_userid, error = _get_userid_for_read()
        if error:
            return error

        if not _can_read_run(token_userid, userid, runid):
            return jsonify({"error": "User cannot view other user's data"}), 403

        # Check if run is deleted
        error_response, status_code = _check_run_not_deleted(userid, runid)
        if error_response:
            return error_response, status_code

        # Parse request body
        req = GetRunExperimentsRequestModel(**(request.json or {}))

        # Get job status to determine if polling can stop
        job_manager = get_job_manager()
        run_details = get_run_details(userid, runid)
        has_job_completed = run_details.is_finished if run_details else False

        # Load experiment tree and convert to models
        tree = ExperimentTree.load(userid=userid, jobid=runid, config=job_manager.config)
        experiment_nodes = tree.to_experiment_models(exclude_experiment_ids=req.known_experiment_ids)
        experiment_models = [ExperimentModel(**node) for node in experiment_nodes]

        resp = GetRunExperimentsResponseModel(
            runid=runid,
            experiments=experiment_models,
            has_job_completed=has_job_completed,
        )
        return jsonify(resp.model_dump()), 200

    @api.route("/<userid>/<runid>/experiments/<experiment_id>", methods=["GET"])
    @optional_enrollment
    def get_run_experiment_details(userid: str, runid: str, experiment_id: str):
        """Fetch details about a specific experiment within a run.

        Args:
            userid: User ID from URL path. Must match authenticated user, be in PUBLIC_USERS,
                    or own a shared run.
            runid: Run identifier
            experiment_id: Experiment identifier
        """
        token_userid, error = _get_userid_for_read()
        if error:
            return error

        if not _can_read_run(token_userid, userid, runid):
            return jsonify({"error": "User cannot view other user's data"}), 403

        # Check if run is deleted
        error_response, status_code = _check_run_not_deleted(userid, runid)
        if error_response:
            return error_response, status_code

        job_manager = get_job_manager()
        node = ExperimentTree.load_node(userid=userid, jobid=runid, experiment_id=experiment_id, config=job_manager.config)

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

    @api.route("/<userid>/<runid>/cancel", methods=["POST"])
    @requires_enrollment
    def cancel_run(userid: str, runid: str):
        """Cancel a running job.

        Args:
            userid: User ID from URL path. Must match authenticated user.
            runid: Run identifier

        Returns:
            JSON response confirming cancellation
        """
        token_userid = request.user.get("sub")
        if not token_userid:
            return jsonify({"error": "User ID not found in token"}), 401

        # Validate that the requesting user owns the run
        if userid != token_userid:
            return jsonify({"error": "User cannot cancel other user's runs"}), 403

        req = CancelRunRequestModel(runid=runid, userid=userid)

        try:
            manager = get_job_manager()

            # Get run details
            run_details = get_run_details(req.userid, req.runid)
            if not run_details:
                return jsonify({"error": "Run details not found"}), 404

            if not run_details.execution_id:
                return jsonify({"error": "Run has not been submitted yet"}), 400

            # Cancel the job
            manager.cancel_job(run_details.execution_id)

            # Update run_details
            update_run_details(
                req.userid,
                req.runid,
                {
                    "status": "CANCELLED",
                    "status_checked_at": datetime.now(UTC).isoformat(),
                },
            )

            resp = CancelRunResponseModel(message="Run cancelled successfully")
            return jsonify(resp.model_dump()), 200

        except Exception as e:
            current_app.logger.error(f"Failed to cancel run: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<userid>/<runid>/bookmark", methods=["POST"])
    @requires_enrollment
    def bookmark_run(userid: str, runid: str):
        """Bookmark or unbookmark a run. Only the run owner can toggle bookmarking.

        Args:
            userid: User ID from URL path. Must match authenticated user.
            runid: Run identifier

        Request body:
            is_bookmarked: boolean - whether to bookmark (true) or unbookmark (false)

        Returns:
            JSON response with updated bookmark status.
        """
        token_userid = request.user.get("sub")
        if not token_userid:
            return jsonify({"error": "User ID not found in token"}), 401

        # Validate that the requesting user owns the run
        if userid != token_userid:
            return jsonify({"error": "User cannot bookmark other user's runs"}), 403

        data = request.get_json()
        if not data or "is_bookmarked" not in data:
            raise BadRequest("is_bookmarked is required")

        try:
            req = BookmarkRunRequestModel(
                runid=runid, userid=userid, is_bookmarked=data["is_bookmarked"]
            )
        except Exception as e:
            raise BadRequest(f"Invalid request body: {e}")

        try:
            manager = get_job_manager()

            # Read current metadata
            metadata_dict = manager.get_metadata(req.userid, req.runid)
            if metadata_dict is None:
                metadata_dict = {}

            # Update is_bookmarked
            metadata_dict["is_bookmarked"] = req.is_bookmarked

            # Write back
            manager.upload_metadata(req.userid, req.runid, metadata_dict)

            resp = BookmarkRunResponseModel(
                is_bookmarked=req.is_bookmarked,
                message="Run bookmarked successfully" if req.is_bookmarked else "Run unbookmarked successfully",
            )
            return jsonify(resp.model_dump()), 200

        except Exception as e:
            current_app.logger.error(f"Failed to bookmark run: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<userid>/<runid>/experiments/<experiment_id>/bookmark", methods=["POST"])
    @requires_enrollment
    def bookmark_experiment(userid: str, runid: str, experiment_id: str):
        """Bookmark or unbookmark an experiment within a run. Only the run owner can toggle bookmarking.

        Args:
            userid: User ID from URL path. Must match authenticated user.
            runid: Run identifier
            experiment_id: Experiment identifier

        Request body:
            is_bookmarked: boolean - whether to bookmark (true) or unbookmark (false)

        Returns:
            JSON response with updated bookmark status for the experiment.
        """
        token_userid = request.user.get("sub")
        if not token_userid:
            return jsonify({"error": "User ID not found in token"}), 401

        if userid != token_userid:
            return jsonify({"error": "User cannot bookmark other user's experiments"}), 403

        data = request.get_json()
        if not data or "is_bookmarked" not in data:
            raise BadRequest("is_bookmarked is required")

        try:
            req = BookmarkExperimentRequestModel(
                runid=runid,
                userid=userid,
                experiment_id=experiment_id,
                is_bookmarked=data["is_bookmarked"],
            )
        except Exception as e:
            raise BadRequest(f"Invalid request body: {e}")

        try:
            manager = get_job_manager()

            metadata_dict = manager.get_metadata(req.userid, req.runid)
            if metadata_dict is None:
                metadata_dict = {}

            ids = set(metadata_dict.get("bookmarked_experiment_ids") or [])
            if req.is_bookmarked:
                ids.add(req.experiment_id)
            else:
                ids.discard(req.experiment_id)
            metadata_dict["bookmarked_experiment_ids"] = list(ids)

            manager.upload_metadata(req.userid, req.runid, metadata_dict)

            resp = BookmarkExperimentResponseModel(
                experiment_id=req.experiment_id,
                is_bookmarked=req.is_bookmarked,
            )
            return jsonify(resp.model_dump()), 200

        except Exception as e:
            current_app.logger.error(f"Failed to bookmark experiment: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<userid>/<runid>/share", methods=["POST"])
    @requires_enrollment
    def share_run(userid: str, runid: str):
        """Share or unshare a run. Only the run owner can toggle sharing.

        Args:
            userid: User ID from URL path. Must match authenticated user.
            runid: Run identifier

        Request body:
            is_shared: boolean - whether to share (true) or unshare (false)

        Returns:
            JSON response with updated sharing status.
        """
        token_userid = request.user.get("sub")
        if not token_userid:
            return jsonify({"error": "User ID not found in token"}), 401

        # Validate that the requesting user owns the run
        if userid != token_userid:
            return jsonify({"error": "User cannot share other user's runs"}), 403

        data = request.get_json()
        if not data or "is_shared" not in data:
            raise BadRequest("is_shared is required")

        try:
            req = ShareRunRequestModel(
                runid=runid, userid=userid, is_shared=data["is_shared"]
            )
        except Exception as e:
            raise BadRequest(f"Invalid request body: {e}")

        try:
            manager = get_job_manager()

            # Read current metadata
            metadata_dict = manager.get_metadata(req.userid, req.runid)
            if metadata_dict is None:
                metadata_dict = {}

            # Update is_shared
            metadata_dict["is_shared"] = req.is_shared

            # Write back
            manager.upload_metadata(req.userid, req.runid, metadata_dict)

            resp = ShareRunResponseModel(
                is_shared=req.is_shared,
                message="Run shared successfully" if req.is_shared else "Run unshared successfully",
            )
            return jsonify(resp.model_dump()), 200

        except Exception as e:
            current_app.logger.error(f"Failed to share run: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/shared/<runid>/owner", methods=["GET"])
    @optional_enrollment
    def get_shared_run_owner(runid: str):
        """Get the owner userid of a shared run.

        This endpoint allows anyone (authenticated or not) to look up the owner
        of a run, but ONLY if the run has is_shared=True in its metadata.json.

        Args:
            runid: Run identifier

        Returns:
            JSON response with runid and userid, or 404 if not found/not shared.

        Security Note:
            Returns 404 for both "run doesn't exist" and "run exists but not shared"
            to avoid information leakage about run existence.
        """
        req = GetSharedRunOwnerRequestModel(runid=runid)

        try:
            manager = get_job_manager()

            # Get the owner userid if the run is shared
            userid = manager.get_shared_run_owner(req.runid)

            if userid is None:
                # Could be: run doesn't exist OR run exists but not shared
                # Return 404 in both cases to prevent information leakage
                return jsonify({"error": "Shared run not found"}), 404

            resp = GetSharedRunOwnerResponseModel(
                runid=req.runid,
                userid=userid
            )
            return jsonify(resp.model_dump()), 200

        except Exception as e:
            current_app.logger.error(f"Failed to get shared run owner for {req.runid}: {e}")
            return jsonify({"error": "Internal server error"}), 500

    return api
