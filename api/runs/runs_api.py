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
from google.cloud import storage
from urllib.parse import urlparse
import logging
import shutil
import subprocess


from flask import Blueprint, current_app, jsonify, request
from utils.auth import (
    PermissionType,
    optional_enrollment,
    requires_auth,
)
from utils.credits import (
    ExperimentLimitExceededError,
    InsufficientCreditsError,
    InvalidExperimentCountError,
    check_experiment_limits,
    get_job_stats,
)
from utils.experiments import ExperimentTree
from utils import copilot_login
from utils.provider_credentials import (
    delete_provider_configuration,
    load_provider_credentials,
    provider_configuration,
    save_provider_configuration,
)
from werkzeug.exceptions import BadRequest

from runs.models import (
    AutoDiscoveryContextModel,
    BookmarkExperimentRequestModel,
    BookmarkExperimentResponseModel,
    BookmarkRunRequestModel,
    BookmarkRunResponseModel,
    CancelRunRequestModel,
    CancelRunResponseModel,
    CreateRunResponseModel,
    DeleteRunRequestModel,
    DeleteRunResponseModel,
    DigDeeperRequestModel,
    DigDeeperResponseModel,
    ExperimentModel,
    ForkRunRequestModel,
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
    GetSharedRunOwnerRequestModel,
    GetSharedRunOwnerResponseModel,
    GetViewerRunsRequestModel,
    GetViewerRunsResponseModel,
    ManifestModel,
    MetadataModel,
    RunDetailsModel,
    RunModel,
    RunStatsModel,
    SaveMetadataRequestModel,
    SaveMetadataResponseModel,
    ShareRunRequestModel,
    ShareRunResponseModel,
    SubmitRunRequestModel,
    SubmitRunResponseModel,
    UploadDatasetResponseModel,
)

# Import autodiscovery_jobs when available
try:
    from autodiscovery_jobs import DATASET_EXPIRY_DAYS, JobConfig, JobManager
    from autodiscovery_jobs.exceptions import (
        CloudRunError,
        DatasetExpiredError,
        GCSError,
        JobAlreadyExistsError,
        JobNotFoundError,
    )
    from autodiscovery_jobs.gcs import (
        get_shared_run_index,
        get_userid_for_job,
        read_rich_outputs,
    )
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

# Max size of files that can be uploaded
UPLOAD_MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 * 1024  # 50GB default
UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_BYTES = 100 * 1024 * 1024 * 1024  # 100GB for users with higher upload limit permission
UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_STR = "100GB"

# Expiration time for presigned upload URLs
UPLOAD_URL_EXPIRATION_SECONDS = 3600  # 1 hour

# Users whose runs are publicly accessible (can be queried by anyone)
PUBLIC_USERS = {"samples"}

_FALLBACK_MODEL_PRICES = (
    ("opus", 5.0, 25.0),
    ("sonnet", 3.0, 15.0),
    ("haiku", 1.0, 5.0),
    ("gpt-5.4", 2.5, 15.0),
    ("gpt-5", 0.25, 2.0),
    ("gemini-3", 0.5, 3.0),
)


def _estimate_local_copilot_cost(job_path: Path, metadata: dict | None) -> float | None:
    """Estimate API-equivalent USD from actual local Copilot token events."""
    if (metadata or {}).get("llm_provider") != "copilot":
        return None
    events_path = job_path / "output" / "llm_usage_events.jsonl"
    if not events_path.is_file():
        return None
    pricing = (metadata or {}).get("model_pricing") or {}
    total_cost = 0.0
    event_count = 0
    for line in events_path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        usage = event.get("usage") or {}
        prompt_tokens = max(0, int(usage.get("prompt_tokens") or 0))
        completion_tokens = max(0, int(usage.get("completion_tokens") or 0))
        if prompt_tokens == 0 and completion_tokens == 0:
            continue
        model = str(event.get("model") or "")
        model_price = pricing.get(model) or {}
        input_rate = model_price.get("input_per_million_usd")
        output_rate = model_price.get("output_per_million_usd")
        if not isinstance(input_rate, (int, float)) or not isinstance(
            output_rate, (int, float)
        ):
            _, input_rate, output_rate = next(
                (entry for entry in _FALLBACK_MODEL_PRICES if entry[0] in model.lower()),
                ("default", 3.0, 15.0),
            )
        total_cost += (prompt_tokens / 1_000_000) * input_rate
        total_cost += (completion_tokens / 1_000_000) * output_rate
        event_count += 1
    return round(total_cost, 6) if event_count else None

# AutoDiscovery's own frontend base URL, used to build a link back to the
# source experiment when handing a user off to Asta.
AUTODISCOVERY_BASE_URL = os.environ.get("AUTODISCOVERY_BASE_URL", "https://autodiscovery.allen.ai")

def sync_preloaded_dataset(source_gs_url, dest_bucket_name, dest_path):
    """Efficiently copies a file between GCS buckets."""
    storage_client = storage.Client()

    # Parse the source URL (gs://source-bucket/path/to/file)
    parsed_url = urlparse(source_gs_url)
    source_bucket_name = parsed_url.netloc
    source_blob_name = parsed_url.path.lstrip('/')

    source_bucket = storage_client.bucket(source_bucket_name)
    source_blob = source_bucket.blob(source_blob_name)

    dest_bucket = storage_client.bucket(dest_bucket_name)
    dest_blob = dest_bucket.blob(dest_path)

    logging.debug(f"GCS SYNC: {source_gs_url} -> gs://{dest_bucket_name}/{dest_path}")

    # Use rewrite instead of download/upload for maximum speed
    rewrite_token = None
    while True:
        rewrite_token, bytes_rewritten, total_bytes = dest_blob.rewrite(
            source_blob, token=rewrite_token
        )
        if rewrite_token is None:
            break

    logging.debug(f"GCS SYNC COMPLETE: {dest_path}")

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

    @api.route("/runtime-config", methods=["GET"])
    def runtime_config():
        """Return credential-free deployment capabilities used by local clients."""
        config = JobConfig.from_env()
        is_local = config.backend == "local"
        return jsonify(
            {
                "deployment_mode": "local" if is_local else "hosted",
                "upload_transport": "api" if is_local else "presigned",
                "hosted_features": not is_local,
            }
        )

    def local_provider_configuration() -> dict:
        """Return fast, secret-free provider configuration state."""
        configured_by_env = any(
            os.environ.get(name) for name in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
        )
        configured_in_keychain = False
        copilot_home = Path(
            os.environ.get(
                "AUTODISCOVERY_COPILOT_HOME",
                Path.home() / ".copilot" / "autodiscovery",
            )
        )
        if os.uname().sysname == "Darwin":
            result = subprocess.run(
                ["security", "find-generic-password", "-s", "copilot-cli"],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )
            configured_in_keychain = result.returncode == 0 and (
                copilot_home / "config.json"
            ).is_file()
        return {
            "copilot": {"configured": configured_by_env or configured_in_keychain},
            **provider_configuration(),
        }

    @api.route("/providers", methods=["GET"])
    def providers():
        """Return provider readiness without credentials or account identifiers."""
        config = JobConfig.from_env()
        if config.backend == "local":
            load_provider_credentials()
        openai_ready = bool(os.environ.get("OPENAI_API_KEY"))
        vertex_ready = bool(
            os.environ.get("VERTEX_ACCESS_TOKEN")
            or os.environ.get("GOOGLE_OAUTH_ACCESS_TOKEN")
        )
        current_models = []
        if openai_ready:
            current_models.extend(["gpt-4o", "o4-mini"])
        if vertex_ready:
            current_models.append("gemini-3-flash-preview")
        current_ready = openai_ready or vertex_ready
        provider_list = [
            {
                "id": "current",
                "name": "OpenAI / Google Vertex",
                "status": "ready" if current_ready else "error",
                "code": "READY" if current_ready else "CREDENTIALS_REQUIRED",
                "message": (
                    "External OpenAI or Google Vertex credentials are available."
                    if current_ready
                    else "No OpenAI or Google Vertex credentials were detected."
                ),
                "remediation": None if current_ready else "Configure provider credentials.",
                "embedding_ready": openai_ready,
                "models": [{"id": model, "name": model, "vision": True} for model in current_models],
            }
        ]
        copilot_configured = (
            config.backend != "local"
            or local_provider_configuration()["copilot"]["configured"]
        )
        if not copilot_configured:
            provider_list.append(
                {
                    "id": "copilot",
                    "name": "GitHub Copilot",
                    "status": "error",
                    "code": "AUTH_REQUIRED",
                    "message": "Copilot is not connected.",
                    "remediation": "Connect GitHub Copilot in Settings.",
                    "embedding_ready": False,
                    "models": [],
                }
            )
        else:
            from autodiscovery.copilot import doctor

            diagnostic = doctor()
            provider_list.append(
                {
                    "id": "copilot",
                    "name": "GitHub Copilot",
                    "status": diagnostic["status"],
                    "code": diagnostic["code"],
                    "message": diagnostic["message"],
                    "remediation": diagnostic["remediation"],
                    "embedding_ready": diagnostic["status"] == "ready",
                    "models": diagnostic["models"],
                }
            )
        return jsonify({"providers": provider_list})

    @api.route("/providers/configuration", methods=["GET"])
    @requires_auth()
    def get_provider_configuration():
        if JobConfig.from_env().backend != "local":
            return jsonify({"error": "Not found"}), 404
        return jsonify({"providers": local_provider_configuration()})

    @api.route("/providers/<provider>/configuration", methods=["PUT", "DELETE"])
    @requires_auth()
    def configure_provider(provider: str):
        if JobConfig.from_env().backend != "local":
            return jsonify({"error": "Not found"}), 404
        try:
            if request.method == "DELETE":
                delete_provider_configuration(provider)
            else:
                save_provider_configuration(provider, request.get_json(silent=True) or {})
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"providers": local_provider_configuration()})

    @api.route("/providers/copilot/login", methods=["POST"])
    @requires_auth()
    def start_copilot_login():
        config = JobConfig.from_env()
        if config.backend != "local":
            return jsonify({"error": "Not found"}), 404
        executable = os.environ.get("COPILOT_CLI_PATH") or shutil.which("copilot")
        if not executable or not Path(executable).is_file():
            return jsonify({"error": "Copilot CLI is not installed"}), 409
        return jsonify(copilot_login.start(executable, config.local_root)), 202

    @api.route("/providers/copilot/login", methods=["GET"])
    @requires_auth()
    def copilot_login_status():
        if JobConfig.from_env().backend != "local":
            return jsonify({"error": "Not found"}), 404
        return jsonify(copilot_login.status())

    @api.route("/providers/copilot/configuration", methods=["DELETE"])
    @requires_auth()
    def disconnect_copilot():
        if JobConfig.from_env().backend != "local":
            return jsonify({"error": "Not found"}), 404
        if any(os.environ.get(name) for name in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")):
            return jsonify({"error": "Copilot authentication is supplied by an environment variable"}), 409
        if os.uname().sysname != "Darwin":
            return jsonify({"error": "Copilot disconnect is only available on macOS"}), 501
        while True:
            result = subprocess.run(
                ["security", "delete-generic-password", "-s", "copilot-cli"],
                capture_output=True,
                check=False,
                text=True,
            )
            if result.returncode != 0:
                break
        return jsonify({"message": "Copilot disconnected"})

    def get_local_storage():
        manager = get_job_manager()
        if manager.config.backend != "local" or manager.local_storage is None:
            raise FileNotFoundError("Local dataset catalog is not available")
        return manager.local_storage

    @api.route("/local-datasets", methods=["GET"])
    @requires_auth()
    def list_local_datasets():
        try:
            storage = get_local_storage()
        except FileNotFoundError:
            return jsonify({"error": "Not found"}), 404
        return jsonify(
            {"datasets": storage.list_datasets(), "catalog_path": str(storage.datasets_root)}
        )

    @api.route("/local-datasets/browse", methods=["POST"])
    @requires_auth()
    def browse_local_dataset_folder():
        try:
            get_local_storage()
        except FileNotFoundError:
            return jsonify({"error": "Not found"}), 404
        if os.uname().sysname != "Darwin":
            return jsonify({"error": "Native folder selection is only available on macOS"}), 501
        result = subprocess.run(
            [
                "osascript",
                "-e",
                'POSIX path of (choose folder with prompt "Choose an AutoDiscovery dataset folder")',
            ],
            capture_output=True,
            check=False,
            text=True,
        )
        return jsonify({"path": result.stdout.strip().rstrip("/") if result.returncode == 0 else None})

    @api.route("/<runid>/local-datasets/import", methods=["POST"])
    @requires_auth()
    def import_local_dataset(runid: str):
        body = request.get_json(silent=True) or {}
        try:
            files = get_local_storage().import_dataset_folder(
                request.user.get("sub"),
                runid,
                dataset_name=body.get("dataset_name"),
                source_path=body.get("source_path"),
            )
        except FileNotFoundError:
            return jsonify({"error": "Not found"}), 404
        except (PermissionError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"files": files})

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
            run_details = create_run_details(userid, runid, manager.config)

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

    @api.route("/fork", methods=["POST"])
    @requires_auth(check_permissions=[PermissionType.HIGHER_UPLOAD_LIMIT])
    def fork_run():
        """Fork an existing run, copying its configuration and dataset files.

        Creates a new run pre-populated with the parent run's metadata
        and a server-side copy of the parent's dataset files.

        Request body:
            parent_run_id: ID of the run to fork from

        Returns:
            JSON response with new runid and GCS path.
        """
        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        body = request.get_json(silent=True) or {}
        try:
            req = ForkRunRequestModel(**body)
        except Exception as e:
            return jsonify({"error": f"Invalid request: {e}"}), 400

        try:
            manager = get_job_manager()

            # Find the parent run's owner.
            # Fast path: the user is almost always forking their own run, so
            # check that first. Fall back to the shared-run index, then to a
            # bucket-wide glob scan (slow) for PUBLIC_USERS or unindexed runs.
            if manager.job_exists(userid, req.parent_run_id):
                parent_userid = userid
            else:
                parent_userid = get_shared_run_index(
                    req.parent_run_id, manager.config
                )
                if not parent_userid:
                    parent_userid = get_userid_for_job(
                        req.parent_run_id, manager.config
                    )
            if not parent_userid:
                return jsonify({"error": "Parent run not found"}), 404

            # Read parent metadata once — reused for permission check AND fork
            parent_metadata = manager.get_metadata(
                parent_userid, req.parent_run_id
            )
            if not parent_metadata:
                return jsonify({"error": "Parent run not found"}), 404

            # Permission check (inlined to avoid re-reading metadata)
            can_read = (
                userid == parent_userid
                or parent_userid in PUBLIC_USERS
                or bool(parent_metadata.get("is_shared"))
            )
            if not can_read:
                return (
                    jsonify({"error": "Cannot access parent run"}),
                    403,
                )

            # Check parent is not deleted
            error_resp, status_code = _check_run_not_deleted(
                parent_userid, req.parent_run_id
            )
            if error_resp:
                return error_resp, status_code

            # Delegate business logic to JobManager, passing metadata to skip re-read
            result = manager.fork_job(
                req.parent_run_id,
                parent_userid,
                userid,
                parent_metadata=parent_metadata,
            )

            # Check upload limit
            has_higher_upload_limit = getattr(
                request, PermissionType.HIGHER_UPLOAD_LIMIT.value, False
            )
            max_file_size = (
                UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_STR
                if has_higher_upload_limit
                else None
            )

            resp = CreateRunResponseModel(
                runid=result.new_run_id,
                path=result.path,
                message="Run forked successfully",
                run_details=RunDetailsModel(
                    **result.run_details.to_dict()
                ),
                max_file_size=max_file_size,
            )
            return jsonify(resp.model_dump()), 200

        except DatasetExpiredError as e:
            return (
                jsonify({"error": "Dataset expired", "message": str(e)}),
                410,
            )
        except ValueError as e:
            return jsonify({"error": str(e)}), 400
        except GCSError as e:
            current_app.logger.error(f"GCS error forking run: {e}")
            return jsonify({"error": str(e)}), 500
        except Exception as e:
            current_app.logger.error(f"Failed to fork run: {e}")
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

    def _compute_dataset_expires_at(run_details: RunDetails | None) -> str | None:
        """Compute dataset expiry timestamp (created_at + DATASET_EXPIRY_DAYS).

        This is an estimate — the actual cleanup cron may run slightly later,
        but using the shared DATASET_EXPIRY_DAYS constant keeps the prediction
        consistent with the deletion threshold.
        """
        if not run_details or not run_details.created_at:
            return None
        try:
            created = datetime.fromisoformat(run_details.created_at)
            expires = created + timedelta(days=DATASET_EXPIRY_DAYS)
            return expires.isoformat()
        except (ValueError, TypeError):
            return None

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
        if job_manager.config.backend == "local" and req.userid in PUBLIC_USERS:
            return jsonify(GetViewerRunsResponseModel(runs=[]).model_dump()), 200
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
                run_details = get_run_details(req.userid, run_id, job_manager.config)
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

            # Compute dataset expiry
            dataset_expires_at = _compute_dataset_expires_at(run_details)

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
                parent_run_id=(
                    run_metadata_model.parent_run_id if run_metadata_model else None
                ),
                parent_run_name=(
                    run_metadata_model.parent_run_name if run_metadata_model else None
                ),
                dataset_expires_at=dataset_expires_at,
                estimated_cost_usd=(
                    _estimate_local_copilot_cost(
                        Path(job_manager.get_job_path(req.userid, run_id)), metadata_dict
                    )
                    if job_manager.config.backend == "local"
                    else None
                ),
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
                run_details = refresh_run_status(req.userid, req.runid, manager.config)
            except Exception as e:
                current_app.logger.error(f"Failed to refresh run status for {req.runid}: {e}")
                run_details = get_run_details(req.userid, req.runid, manager.config)

            # Drafts have no output, and the hosted stats helper would otherwise query GCS.
            if manager.config.backend == "local" and not (
                run_details and run_details.execution_id
            ):
                job_stats = None
            else:
                try:
                    job_stats = get_job_stats(
                        userid=req.userid, jobid=req.runid, config=manager.config
                    )
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

            # Check if user has permission for access in the UI
            has_ai1_datasets = PermissionType.AI1_DATASETS.value in permissions

            # Compute dataset expiry
            dataset_expires_at = _compute_dataset_expires_at(run_details)

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
                can_view_datasets=has_ai1_datasets,
                can_explore_with_asta=True,  # Enabled for all users (no longer permission-gated)
                parent_run_id=(
                    run_metadata_model.parent_run_id if run_metadata_model else None
                ),
                parent_run_name=(
                    run_metadata_model.parent_run_name if run_metadata_model else None
                ),
                dataset_expires_at=dataset_expires_at,
                estimated_cost_usd=(
                    _estimate_local_copilot_cost(Path(path), metadata_dict)
                    if manager.config.backend == "local"
                    else None
                ),
            )

            return jsonify(run_model.model_dump()), 200

        except Exception as e:
            current_app.logger.error(f"Failed to get run details: {e}")
            return jsonify({"error": str(e)}), 500

    @api.route("/<runid>", methods=["DELETE"])
    @requires_auth()
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
    @requires_auth()
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
    @requires_auth()
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
            path = manager.upload_metadata(req.userid, req.runid, req.metadata.to_storage_dict())
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
    @requires_auth()
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

        # Check if user has AI1_DATASETS permission for dataset access in the UI
        permissions = request.user.get("permissions", [])
        has_ai1_permission = PermissionType.AI1_DATASETS.value in permissions

        req = SubmitRunRequestModel(runid=runid_data, userid=userid)

        try:
            manager = get_job_manager()

            # Read job configuration from metadata
            metadata = manager.get_metadata(req.userid, req.runid)
            if not metadata:
                raise BadRequest("Run metadata not found. Please save run configuration first.")

            if manager.config.backend == "local":
                if metadata.get("llm_provider") != "copilot":
                    raise BadRequest(
                        "Local runs require GitHub Copilot. Choose a Copilot model in the run settings."
                    )
                from autodiscovery.copilot import doctor

                diagnostic = doctor()
                if diagnostic["status"] != "ready":
                    raise BadRequest(
                        diagnostic.get("remediation")
                        or "GitHub Copilot is not ready. Complete sign-in in Settings."
                    )
                available_models = {
                    model["id"] for model in diagnostic["models"] if model.get("id")
                }
                if metadata.get("model") not in available_models:
                    raise BadRequest(
                        "Choose an available GitHub Copilot model in the run settings before starting."
                    )

            datasets = metadata.get("datasets", [])
            for ds in datasets:
                # If the dataset has a URL, it's an S3 preloaded file
                if (
                    manager.config.backend != "local"
                    and ds.get("url")
                    and ds.get("url").startswith("gs://")
                ):
                    if not has_ai1_permission:
                        return jsonify({"error": "Permission denied for preloaded datasets"}), 403
                    filename = ds.get("name")
                    source_url = ds.get("url")

                    gcs_dest_path = f"users/{req.userid}/jobs/{req.runid}/data/{filename}"
                    try:
                        sync_preloaded_dataset(
                            source_gs_url=source_url,
                            dest_bucket_name=manager.config.bucket,
                            dest_path=gcs_dest_path
                        )
                    except Exception as e:
                        current_app.logger.error(f"Failed to sync preloaded dataset {filename}: {e}")
                        return jsonify({"error": f"Failed to prepare preloaded dataset: {str(e)}"}), 500

            intent = metadata.get("intent", "")
            n_experiments = metadata.get("n_experiments")

            if n_experiments is None:
                raise BadRequest("Number of Experiments is required in metadata")

            # Validate experiment count and sufficient credits before submission
            if manager.config.backend != "local":
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
                "model",
                "belief_model",
                "vision_model",
                "llm_provider",
                "embedding_provider",
                "embedding_model",
                "embedding_dimensions",
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
                manager.config,
            )

            # Get updated run_details to return to frontend
            run_details = get_run_details(req.userid, req.runid, manager.config)
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

        except BadRequest as e:
            return jsonify({"error": e.description}), 400

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
    @requires_auth()
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
    @requires_auth()
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
    @requires_auth()
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
    @requires_auth()
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

            manager.set_run_shared(req.runid, req.userid, req.is_shared)

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

    @api.route("/<userid>/<runid>/experiments/<experiment_id>/dig-deeper", methods=["POST"])
    @requires_auth()
    def dig_deeper_with_asta(userid: str, runid: str, experiment_id: str):  # pyright: ignore reportUnusedFunction
        """Create an Asta context handoff from an AutoDiscovery experiment node.

        Saves a manifest.json and a copy of the dataset to the Asta workspace
        GCS bucket, then fires an A2A message/send to Asta DataVoyager.

        Returns the Asta chat URL and the GCS URI of the saved manifest.
        """
        import requests as _requests

        import utils.asta_client as asta_client
        import utils.asta_context_client as asta_context_client
        from autodiscovery_jobs import asta_gcs

        if not JOBS_AVAILABLE:
            return jsonify({"error": "Job management not available"}), 503

        caller_id = request.user.get("sub")
        if caller_id != userid:
            return jsonify({"error": "Unauthorized"}), 403

        body = request.get_json(silent=True) or {}
        try:
            req = DigDeeperRequestModel(**body)
        except Exception:
            return jsonify({"error": "Missing or invalid 'query' field"}), 400

        job_manager = get_job_manager()
        config = job_manager.config

        # Load run metadata for description and dataset_description
        try:
            metadata = job_manager.get_metadata(userid, runid)
        except Exception as e:
            current_app.logger.error("Failed to load metadata for run %s: %s", runid, e)
            return jsonify({"error": "Run not found"}), 404

        description = metadata.get("description")
        datasets = metadata.get("datasets") or []
        dataset_description = datasets[0].get("description") if datasets else None

        # Load just the target experiment node
        target_node = ExperimentTree.load_node(userid, runid, experiment_id, config)
        if target_node is None:
            return jsonify({"error": f"Experiment {experiment_id} not found"}), 404

        source_code = target_node.code

        # Extract figure descriptions from rich outputs on the target node
        figure_descriptions: list[str] = []
        try:
            rich_outputs = read_rich_outputs(userid, runid, target_node.level, target_node.index, config)
            for i, bundle in enumerate(rich_outputs):
                text = bundle.get("text/plain") or bundle.get("text/markdown")
                figure_descriptions.append(text.strip() if text else f"Figure {i + 1}")
        except Exception as e:
            current_app.logger.warning("Could not read rich outputs for %s: %s", experiment_id, e)

        # Build the manifest
        context = AutoDiscoveryContextModel(
            hypothesis=target_node.hypothesis,
            experiment_plan=target_node.experiment_plan,
            analysis=target_node.analysis,
            source_code=source_code,
            stdout=target_node.code_output,
            figure_descriptions=figure_descriptions,
        )
        manifest = ManifestModel(
            query=req.query,
            description=description,
            dataset_description=dataset_description,
            autodiscovery_context=context,
        )

        # Fetch full user profile from Auth0 for the Asta login call.
        # Asta's login falls back to matching by email when auth0_user_id doesn't
        # match an existing record (e.g. the user authenticated via a different
        # Auth0 connection than before), so a missing/bad email here can cause
        # Asta to create a duplicate account instead of recognizing a returning
        # user. Retry once on transient failures rather than sending fake data.
        auth0_user_id = request.user.get("sub", "")
        auth0_domain = os.environ.get("AUTH0_DOMAIN", "")
        token = (request.headers.get("Authorization", "") or "").split()[-1]

        userinfo = None
        if token and auth0_domain:
            for attempt in range(2):
                try:
                    info = _requests.get(
                        f"https://{auth0_domain}/userinfo",
                        headers={"Authorization": f"Bearer {token}"},
                        timeout=10,
                    )
                    info.raise_for_status()
                    userinfo = info.json()
                    break
                except Exception as e:
                    current_app.logger.warning(
                        "Auth0 userinfo fetch failed (attempt %d/2): %s", attempt + 1, e
                    )

        if userinfo is None:
            current_app.logger.error(
                "Could not fetch Auth0 userinfo for user %s", auth0_user_id
            )
            return jsonify({"error": "Failed to fetch user profile from Auth0"}), 502

        email = userinfo.get("email", "")
        name = userinfo.get("name", email)
        nickname = userinfo.get("nickname", email)

        try:
            user_uuid = asta_client.login_or_create_user(
                auth0_user_id=auth0_user_id,
                email=email,
                name=name,
                nickname=nickname,
            )
        except Exception as e:
            current_app.logger.error("Asta login failed: %s", e)
            return jsonify({"error": "Failed to authenticate with Asta"}), 502

        autodiscovery_link = f"{AUTODISCOVERY_BASE_URL}/runs/{runid}?exp={target_node.creation_idx - 1}"

        try:
            thread_id = asta_client.create_thread(token, autodiscovery_link=autodiscovery_link)
        except Exception as e:
            current_app.logger.error("Asta thread creation failed: %s", e)
            return jsonify({"error": "Failed to create Asta thread"}), 502

        asta_url = f"{asta_client.ASTA_BASE_URL}/chat/{thread_id}"

        # Upload manifest.json through the context service so it is tracked.
        # The service writes the object + metadata row and returns its gs:// path.
        deletable_date = (datetime.now(UTC) + timedelta(days=30)).date().isoformat()
        try:
            manifest_gcs_uri = asta_context_client.upload_json_artifact(
                owner_id=user_uuid,
                prefix=thread_id,
                filename="manifest.json",
                content=manifest.model_dump(),
                artifact_type="manifest",
                source="autodiscovery",
                tags=[f"dataset_deletable_date:{deletable_date}"],
            )
        except Exception as e:
            current_app.logger.error("Failed to upload manifest to context service: %s", e)
            return jsonify({"error": "Failed to save context to storage"}), 500

        # Copy dataset files — required for Asta to load the data.
        try:
            dataset_uris = asta_gcs.copy_dataset_to_asta_workspace(userid, runid, user_uuid, thread_id, config)
            current_app.logger.info("Copied %d dataset file(s) to Asta workspace", len(dataset_uris))
        except Exception as e:
            current_app.logger.error("Dataset copy failed: %s", e)
            return jsonify({"error": "Failed to copy dataset to Asta workspace"}), 500

        dataset_attachments = "".join(
            f'\n<astaattachment type="dataset" gcs_uri="{uri}">{uri.split("/")[-1]}</astaattachment>'
            for uri in dataset_uris
        )
        formatted_query = (
            f"{req.query}\n\n"
            f'<astaattachment type="analysis_context" gcs_uri="{manifest_gcs_uri}">Autodiscovery_context.json</astaattachment>'
            f"{dataset_attachments}"
        )

        # Fire message (best-effort: manifest is already saved regardless)
        current_app.logger.info("Firing A2A message: thread_id=%s", thread_id)
        try:
            asta_client.send_dig_deeper_message(thread_id, formatted_query, token)
            current_app.logger.info("A2A message sent successfully: thread_id=%s", thread_id)
        except Exception as e:
            current_app.logger.error("A2A message failed (non-fatal): %s", e)

        return jsonify(
            DigDeeperResponseModel(asta_url=asta_url, manifest_gcs_uri=manifest_gcs_uri).model_dump()
        ), 200

    return api
