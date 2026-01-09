"""Smoke test for ModalSandboxIPythonBackend with a GCS dataset mount."""

from __future__ import annotations

import logging
import os

import modal
from autodiscovery_modal import ModalSandboxIPythonBackend
from code_execution import IPythonExecutor


def main() -> None:
    """Run a basic sandbox execution and list the dataset mount."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    app_name = os.environ.get("MODAL_APP_NAME", "asta-autodiscovery")
    bucket = os.environ.get("GCS_BUCKET", "example-gcp-project")
    key_prefix = os.environ.get("GCS_PREFIX", "samples/")
    read_only = os.environ.get("GCS_READ_ONLY", "true").lower() == "true"
    bucket_endpoint_url = os.environ.get("GCS_ENDPOINT_URL", "https://storage.googleapis.com")
    mount_path = "/data"

    secret_name = os.environ.get("MODAL_BUCKET_SECRET", "example-bucket-secret")
    if not secret_name:
        raise ValueError("Set MODAL_BUCKET_SECRET to a Modal Secret with GCS credentials.")

    bucket_secret = modal.Secret.from_name(secret_name)
    backend = ModalSandboxIPythonBackend.for_bucket_prefix(
        app_name=app_name,
        bucket=bucket,
        key_prefix=key_prefix,
        mount_path=mount_path,
        read_only=read_only,
        bucket_endpoint_url=bucket_endpoint_url,
        bucket_secret=bucket_secret,
        env={"SMOKE_TEST": "true"},
    )

    executor = IPythonExecutor(backend)
    code_str = f"""
from pathlib import Path

for p in sorted(Path({mount_path!r}).iterdir()):
    print(p.name)
"""
    result = executor.run_cell(code_str)

    logging.info(result["stdout"])
    logging.info("success: %s", result["success"])


if __name__ == "__main__":
    main()
