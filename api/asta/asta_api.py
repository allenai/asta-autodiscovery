"""Asta dataset imports and experiment handoffs, served under the runs API prefix."""

import os
from datetime import UTC, datetime, timedelta

import requests
from autodiscovery_jobs import JobConfig, JobManager
from autodiscovery_jobs.persistence import dataset_key, read_rich_outputs
from autodiscovery_jobs.storage import get_store
from flask import Blueprint, current_app, jsonify, request
from runs.datasets import UPLOAD_MAX_FILE_SIZE_BYTES, UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_BYTES
from runs.models import UploadDatasetResponseModel
from utils.auth import PermissionType, requires_auth
from utils.experiments import ExperimentTree
from werkzeug.exceptions import BadRequest

from asta import client, context_client, workspace
from asta.context_client import is_configured as is_enabled
from asta.models import (
    AutoDiscoveryContextModel,
    DigDeeperRequestModel,
    DigDeeperResponseModel,
    ImportContextArtifactRequestModel,
    ManifestModel,
)

# AutoDiscovery's own frontend base URL, used to build a link back to the
# source experiment when handing a user off to Asta.
AUTODISCOVERY_BASE_URL = os.environ.get("AUTODISCOVERY_BASE_URL", "https://autodiscovery.allen.ai")


def _access_token() -> str:
    """Read the bearer token, including when authentication is disabled locally."""
    parts = (request.headers.get("Authorization", "") or "").split()
    return parts[-1] if parts else ""


def _resolve_asta_user_uuid() -> tuple[str | None, tuple | None]:
    """Map the authenticated Auth0 user to their Asta UUID for either integration."""
    auth0_user_id = request.user.get("sub", "")
    auth0_domain = os.environ.get("AUTH0_DOMAIN", "")
    token = _access_token()

    # Asta can match returning users by email. Fetch their real profile and retry
    # transient failures rather than sending placeholder data that creates duplicates.
    userinfo = None
    if token and auth0_domain:
        for attempt in range(2):
            try:
                info = requests.get(
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
        return None, (jsonify({"error": "Failed to fetch user profile from Auth0"}), 502)

    email = userinfo.get("email", "")
    try:
        return client.login_or_create_user(
            auth0_user_id=auth0_user_id,
            email=email,
            name=userinfo.get("name", email),
            nickname=userinfo.get("nickname", email),
        ), None
    except Exception as e:
        current_app.logger.error("Asta login failed: %s", e)
        return None, (jsonify({"error": "Failed to authenticate with Asta"}), 502)


def create() -> Blueprint:
    """Create the Asta integration blueprint.

    Returns:
        Flask Blueprint with dataset import and dig-deeper endpoints.
    """
    api = Blueprint("asta_api", __name__)

    @api.route("/<runid>/import-context-artifact", methods=["POST"])
    @requires_auth(check_permissions=[PermissionType.HIGHER_UPLOAD_LIMIT])
    def import_context_artifact(runid: str):
        """Copy one of the caller's Asta context-service artifacts into the run's data.

        An alternative to uploading: the file lands at the same data key an upload
        would, so metadata and the job runner treat it exactly like an uploaded file.
        Only available when the Asta integration is configured.
        """
        if not is_enabled():
            return jsonify({"error": "Asta integration is not configured"}), 404

        userid = request.user.get("sub")
        if not userid:
            return jsonify({"error": "User ID not found in token"}), 401

        try:
            req = ImportContextArtifactRequestModel(**(request.get_json(silent=True) or {}))
        except Exception as e:
            raise BadRequest(f"Invalid request: {e}") from e

        manager = JobManager(JobConfig.from_env())
        if not manager.job_exists(userid, runid):
            return jsonify({"error": f"Run {runid} not found"}), 404

        user_uuid, err = _resolve_asta_user_uuid()
        if err:
            return err

        try:
            artifact = context_client.find_owned_artifact(user_uuid, req.artifact_id)
        except Exception as e:
            current_app.logger.error("Context-service artifact lookup failed: %s", e)
            return jsonify({"error": "Failed to look up Asta artifact"}), 502
        if artifact is None:
            return jsonify({"error": f"Artifact {req.artifact_id} not found"}), 404

        filename = req.filename or artifact.get("filename") or ""
        if not filename or "/" in filename or "\\" in filename or filename in (".", ".."):
            raise BadRequest("Invalid filename")

        has_higher_limit = getattr(request, PermissionType.HIGHER_UPLOAD_LIMIT.value, False)
        max_file_size = (
            UPLOAD_MAX_FILE_SIZE_HIGHER_LIMIT_BYTES
            if has_higher_limit
            else UPLOAD_MAX_FILE_SIZE_BYTES
        )
        size = artifact.get("file_size_bytes")
        if isinstance(size, int) and size > max_file_size:
            return jsonify({"error": "File too large."}), 413

        try:
            download_url = context_client.get_download_url(req.artifact_id)
            with requests.get(download_url, stream=True, timeout=(10, 300)) as src:
                src.raise_for_status()
                if int(src.headers.get("Content-Length") or 0) > max_file_size:
                    return jsonify({"error": "File too large."}), 413
                src.raw.decode_content = True
                key = dataset_key(userid, runid, filename)
                store = get_store(manager.config)
                store.write_stream(
                    key,
                    src.raw,
                    content_type=artifact.get("content_type") or src.headers.get("Content-Type"),
                )
        except Exception as e:
            current_app.logger.error("Failed to import context artifact: %s", e)
            return jsonify({"error": "Failed to import Asta artifact"}), 502

        resp = UploadDatasetResponseModel(
            path=store.uri(key),
            filename=filename,
            message="Dataset imported from Asta",
        )
        return jsonify(resp.model_dump()), 200

    @api.route("/<userid>/<runid>/experiments/<experiment_id>/dig-deeper", methods=["POST"])
    @requires_auth()
    def dig_deeper_with_asta(userid: str, runid: str, experiment_id: str):  # pyright: ignore reportUnusedFunction
        """Create an Asta context handoff from an AutoDiscovery experiment node.

        Saves a manifest.json and a copy of the dataset to the Asta workspace
        GCS bucket, then fires an A2A message/send to Asta DataVoyager.

        Returns the Asta chat URL and the GCS URI of the saved manifest.
        """
        # The UI hides this feature when unconfigured, but guard here too so a
        # direct call fails cleanly instead of reaching out to asta.allen.ai.
        if not is_enabled():
            return jsonify({"error": "Asta integration is not configured"}), 503

        caller_id = request.user.get("sub")
        if caller_id != userid:
            return jsonify({"error": "Unauthorized"}), 403

        body = request.get_json(silent=True) or {}
        try:
            req = DigDeeperRequestModel(**body)
        except Exception:
            return jsonify({"error": "Missing or invalid 'query' field"}), 400

        config = JobConfig.from_env()
        job_manager = JobManager(config)

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
            rich_outputs = read_rich_outputs(
                userid, runid, target_node.level, target_node.index, config
            )
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

        user_uuid, err = _resolve_asta_user_uuid()
        if err:
            return err
        token = _access_token()

        autodiscovery_link = (
            f"{AUTODISCOVERY_BASE_URL}/runs/{runid}?exp={target_node.creation_idx - 1}"
        )

        try:
            thread_id = client.create_thread(token, autodiscovery_link=autodiscovery_link)
        except Exception as e:
            current_app.logger.error("Asta thread creation failed: %s", e)
            return jsonify({"error": "Failed to create Asta thread"}), 502

        asta_url = f"{client.ASTA_BASE_URL}/chat/{thread_id}"

        # Upload manifest.json through the context service so it is tracked.
        # The service writes the object + metadata row and returns its gs:// path.
        deletable_date = (datetime.now(UTC) + timedelta(days=30)).date().isoformat()
        try:
            manifest_gcs_uri = context_client.upload_json_artifact(
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
            dataset_uris = workspace.copy_dataset_to_asta_workspace(
                userid, runid, user_uuid, thread_id, config
            )
            current_app.logger.info(
                "Copied %d dataset file(s) to Asta workspace", len(dataset_uris)
            )
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
            client.send_dig_deeper_message(thread_id, formatted_query, token)
            current_app.logger.info("A2A message sent successfully: thread_id=%s", thread_id)
        except Exception as e:
            current_app.logger.error("A2A message failed (non-fatal): %s", e)

        return jsonify(
            DigDeeperResponseModel(
                asta_url=asta_url, manifest_gcs_uri=manifest_gcs_uri
            ).model_dump()
        ), 200

    return api
