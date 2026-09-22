"""Local Docker job backend.

Launches AutoDiscovery jobs as local Docker containers via the host Docker
daemon (reached through a mounted ``/var/run/docker.sock``). The launched job
runs the same AD image with the same CLI arguments as the Cloud Run backend —
only the process launcher differs.

Cloud Run provides the job's data as a GCS volume; locally this backend
bind-mounts the run's own directory from the host data directory instead, which
is why it requires ``STORAGE_BACKEND=local`` (enforced at startup by
``JobManager``). The mount is **scoped to the current run's prefix** and appears
at :data:`JOB_MOUNT_ROOT` under the same deep path Cloud Run uses, so the job
arguments are identical across job backends.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

from ..exceptions import DockerBackendError
from ..keys import job_dir
from .base import JOB_MOUNT_ROOT, JobBackend, build_job_args

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
    "VERTEXAI_PROJECT",
    "VERTEXAI_LOCATION",
    "GCP_PROJECT",
    "GCS_BUCKET",
)

# In-container path where the GCP credentials file is mounted, for jobs that use
# Google-hosted models (Vertex AI). Matches the API container's
# GOOGLE_APPLICATION_CREDENTIALS convention in docker-compose.
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

        # Forward the secrets/env the job needs.
        environment: dict[str, str] = {
            k: os.environ[k] for k in _JOB_ENV_PASSTHROUGH if os.environ.get(k)
        }
        volumes: dict[str, dict[str, str]] = {}

        # Bind-mount the run's own directory, scoped to its prefix and mounted at
        # the same deep path build_job_args expects so the args are unchanged. This
        # keeps other users' data out of the container even when code runs
        # in-process (CODE_EXECUTION_BACKEND=process/local). Unlike Cloud Run's
        # fixed job-level mount, the Docker backend can scope per run.
        prefix = job_dir(userid, jobid)
        volumes[self._host_run_dir(prefix)] = {
            "bind": f"{JOB_MOUNT_ROOT}/{prefix}",
            "mode": "rw",
        }

        # Forward GCP credentials when available, for Google-hosted models. In
        # docker-out-of-docker the bind source must be a *host* path, so it is
        # provided out-of-band via GCP_KEY_HOST_PATH (the same file docker-compose
        # binds into the API).
        host_key_path = os.environ.get("GCP_KEY_HOST_PATH")
        if host_key_path:
            volumes[host_key_path] = {"bind": _CONTAINER_GCP_KEY_PATH, "mode": "ro"}
            environment["GOOGLE_APPLICATION_CREDENTIALS"] = _CONTAINER_GCP_KEY_PATH

        client = _docker_client()
        try:
            client.containers.run(
                image=self.config.job_image,
                command=args,
                name=execution_id,
                detach=True,
                environment=environment,
                volumes=volumes,
            )
        except Exception as e:
            raise DockerBackendError(f"Failed to launch job container: {e}") from e

        return execution_id

    def _host_run_dir(self, prefix: str) -> str:
        """Return the **host** path of a run's data directory for a bind mount.

        ``config.storage_dir`` is where the data directory is mounted inside *this*
        (API) container, which is unusable as a bind source for the host daemon in
        docker-out-of-docker. The host path is supplied out-of-band via
        ``STORAGE_HOST_DIR``, exactly as ``GCP_KEY_HOST_PATH`` supplies the key's.
        When unset — i.e. this process is not containerized — ``storage_dir`` is
        already a host path.

        Raises:
            DockerBackendError: If the resolved path is not absolute; the host
                daemon has no working directory to resolve it against.
        """
        host_root = os.environ.get("STORAGE_HOST_DIR") or self.config.storage_dir
        if not Path(host_root).is_absolute():
            raise DockerBackendError(
                f"Storage host directory {host_root!r} must be an absolute path so the "
                "Docker daemon can bind-mount it into job containers. Set STORAGE_HOST_DIR "
                "(or STORAGE_DIR when the API is not containerized) to an absolute path."
            )
        return f"{host_root.rstrip('/')}/{prefix}"

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
