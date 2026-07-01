"""Backward-compatibility shim for the Cloud Run job backend.

The Cloud Run implementation now lives in
:mod:`autodiscovery_jobs.backends.gcp`. This module re-exports its functional
API so existing imports (``from autodiscovery_jobs import cloudrun`` /
``from autodiscovery_jobs.cloudrun import run_job``) keep working. New code
should use :func:`autodiscovery_jobs.backends.get_backend` instead.
"""

from __future__ import annotations

from .backends.gcp import (
    cancel_job,
    get_job_logs,
    get_job_status,
    run_job,
)

__all__ = [
    "run_job",
    "get_job_status",
    "cancel_job",
    "get_job_logs",
]
