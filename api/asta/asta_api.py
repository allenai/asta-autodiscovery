"""The "dig deeper" handoff of an AutoDiscovery experiment to Asta.

Served under the runs API's URL prefix, since it acts on a run's experiment.
"""

import os
from datetime import UTC, datetime, timedelta

import requests
from autodiscovery_jobs import JobConfig, JobManager
from autodiscovery_jobs.persistence import read_rich_outputs
from flask import Blueprint, current_app, jsonify, request
from utils.auth import requires_auth
from utils.experiments import ExperimentTree

from asta import client, context_client, workspace
from asta.context_client import is_configured as is_enabled
from asta.models import (
    AutoDiscoveryContextModel,
    DigDeeperRequestModel,
    DigDeeperResponseModel,
    ManifestModel,
)

# AutoDiscovery's own frontend base URL, used to build a link back to the
# source experiment when handing a user off to Asta.
AUTODISCOVERY_BASE_URL = os.environ.get("AUTODISCOVERY_BASE_URL", "https://autodiscovery.allen.ai")


def create() -> Blueprint:
    """Create the Asta handoff blueprint.

    Returns:
        Flask Blueprint with the dig-deeper endpoint.
    """
    api = Blueprint("asta_api", __name__)

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
            current_app.logger.error("Could not fetch Auth0 userinfo for user %s", auth0_user_id)
            return jsonify({"error": "Failed to fetch user profile from Auth0"}), 502

        email = userinfo.get("email", "")
        name = userinfo.get("name", email)
        nickname = userinfo.get("nickname", email)

        try:
            user_uuid = client.login_or_create_user(
                auth0_user_id=auth0_user_id,
                email=email,
                name=name,
                nickname=nickname,
            )
        except Exception as e:
            current_app.logger.error("Asta login failed: %s", e)
            return jsonify({"error": "Failed to authenticate with Asta"}), 502

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
