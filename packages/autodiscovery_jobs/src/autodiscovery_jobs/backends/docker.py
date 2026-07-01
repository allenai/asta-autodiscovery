"""Local Docker job backend.

Launches AutoDiscovery jobs as local Docker containers via the host Docker
daemon (reached through a mounted ``/var/run/docker.sock``). The launched job
runs the same AD image with the same CLI arguments as the Cloud Run backend and
continues to use Modal for its code-execution sandboxes — only the process
launcher differs.

Because there is no Cloud Run GCS FUSE volume locally, the job container mounts
the real bucket at ``/mnt/gcs`` itself via gcsfuse in its entrypoint. This
backend enables that by passing ``GCSFUSE_BUCKET`` plus GCP credentials and the
``/dev/fuse`` device / ``SYS_ADMIN`` capability to the container.
"""

from __future__ import annotations

import os
import uuid
from typing import Any

from ..exceptions import DockerBackendError
from .base import JobBackend, build_job_args

# Environment variables forwarded from the API container to each job container.
# These mirror the secrets/env the Cloud Run job receives (see
# packages/autodiscovery/scripts/rebuild_and_deploy.sh). Only vars that are
# actually set on the API container are forwarded.
_JOB_ENV_PASSTHROUGH = (
    "OPENAI_API_KEY",
    "MODAL_TOKEN_ID",
    "MODAL_TOKEN_SECRET",
    "MODAL_ENVIRONMENT",
    "MODAL_IMAGE_BUILDER_VERSION",
    "MODAL_APP_NAME",
    "MODAL_BUCKET_SECRET",
    "VERTEX_PROJECT_ID",
    "VERTEX_LOCATION",
    "GCP_PROJECT",
    "GCS_BUCKET",
)

# In-container path where the GCP credentials file is mounted (matches the API
# container's GOOGLE_APPLICATION_CREDENTIALS convention in docker-compose).
_CONTAINER_GCP_KEY_PATH = "/secrets/gcp-key.json"


def _docker_client():
    """Return a Docker SDK client, raising a helpful error if unavailable."""
    try:
        import docker
    except ImportError as e:  # pragma: no cover - dependency wiring
        raise DockerBackendError(
            "The 'docker' Python package is required for the Docker job backend. "
            "Install it (added as a dependency of asta-autodiscovery-jobs)."
        ) from e

    try:
        return docker.from_env()
    except Exception as e:
        raise DockerBackendError(
            f"Could not connect to the Docker daemon. Is /var/run/docker.sock mounted? {e}"
        ) from e


class DockerBackend(JobBackend):
    """:class:`JobBackend` that launches jobs as local Docker containers.

    The ``execution_id`` returned by :meth:`run_job` is the container name, and
    is passed back to the other methods to inspect / stop / read logs.
    """

    def run_job(self, userid: str, jobid: str, **kwargs) -> str:
        """Launch the AD job as a local container and return its container name."""
        args = build_job_args(userid, jobid, self.config, **kwargs)

        if not self.config.job_image:
            raise DockerBackendError(
                "config.job_image must be set for the Docker backend. Set it via "
                "config.job_image or the AUTODISCOVERY_IMAGE environment variable."
            )

        # Unique, inspectable container name used as the execution_id.
        execution_id = f"{self.config.job_name}-{uuid.uuid4().hex[:8]}"

        # Forward the secrets/env the job needs, plus the gcsfuse trigger.
        environment: dict[str, str] = {
            k: os.environ[k] for k in _JOB_ENV_PASSTHROUGH if os.environ.get(k)
        }
        environment["GCSFUSE_BUCKET"] = self.config.bucket
        environment["GOOGLE_APPLICATION_CREDENTIALS"] = _CONTAINER_GCP_KEY_PATH

        # Bind-mount the GCP credentials file so gcsfuse (and google-cloud
        # clients) can authenticate. In docker-out-of-docker the bind source
        # must be a *host* path, so it is provided out-of-band via
        # GCP_KEY_HOST_PATH (the same file docker-compose binds into the API).
        volumes: dict[str, dict[str, str]] = {}
        host_key_path = os.environ.get("GCP_KEY_HOST_PATH")
        if host_key_path:
            volumes[host_key_path] = {"bind": _CONTAINER_GCP_KEY_PATH, "mode": "ro"}

        client = _docker_client()
        try:
            client.containers.run(
                image=self.config.job_image,
                command=args,
                name=execution_id,
                detach=True,
                environment=environment,
                volumes=volumes,
                # gcsfuse inside the container needs FUSE + mount privileges.
                devices=["/dev/fuse"],
                cap_add=["SYS_ADMIN"],
                security_opt=["apparmor:unconfined"],
            )
        except Exception as e:
            raise DockerBackendError(f"Failed to launch job container: {e}") from e

        return execution_id

    def _get_container(self, execution_id: str):
        client = _docker_client()
        try:
            return client.containers.get(execution_id)
        except Exception as e:
            raise DockerBackendError(f"Job container '{execution_id}' not found: {e}") from e

    def get_job_status(self, execution_id: str) -> dict[str, Any]:
        """Return status info for the job container, mapped to shared phases."""
        container = self._get_container(execution_id)
        state = container.attrs.get("State", {})
        status = state.get("Status", "")
        exit_code = state.get("ExitCode", 0)

        phase = _phase_from_state(status, exit_code)

        created = container.attrs.get("Created")
        started = state.get("StartedAt")
        finished = state.get("FinishedAt")

        return {
            "name": execution_id,
            "phase": phase,
            "create_time": created,
            "start_time": _clean_time(started),
            "completion_time": _clean_time(finished),
            "status": status,
            "exit_code": exit_code,
        }

    def cancel_job(self, execution_id: str) -> None:
        """Stop the job container."""
        container = self._get_container(execution_id)
        try:
            container.stop(timeout=10)
        except Exception as e:
            raise DockerBackendError(f"Failed to cancel job container '{execution_id}': {e}") from e

    def get_job_logs(self, execution_id: str | None = None, limit: int = 50) -> list[str]:
        """Return recent log lines from the job container."""
        if not execution_id:
            # Unlike Cloud Run's central log store, Docker logs are per-container;
            # there is nothing to return without a specific container.
            return []
        container = self._get_container(execution_id)
        try:
            raw = container.logs(tail=limit)
        except Exception as e:
            raise DockerBackendError(
                f"Failed to get logs for job container '{execution_id}': {e}"
            ) from e
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
        return [line for line in text.splitlines() if line]


def _phase_from_state(status: str, exit_code: int) -> str:
    """Map a Docker container State to the shared phase vocabulary."""
    if status in ("running", "restarting", "paused", "removing"):
        return "RUNNING"
    if status == "created":
        return "PENDING"
    if status == "exited":
        return "SUCCEEDED" if exit_code == 0 else "FAILED"
    if status == "dead":
        return "FAILED"
    return "PENDING"


def _clean_time(value: str | None) -> str | None:
    """Normalize Docker's zero-value timestamps to None."""
    if not value or value.startswith("0001-01-01"):
        return None
    return value
