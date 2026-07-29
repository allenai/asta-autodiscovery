"""Backward-compatibility shim for the job-data persistence API.

Persistence is no longer GCS-specific: the functional API now lives in
:mod:`autodiscovery_jobs.persistence` and runs against whichever
:class:`~autodiscovery_jobs.storage.ObjectStore` ``STORAGE_BACKEND`` selects.
This module re-exports it so existing imports (``from autodiscovery_jobs import
gcs`` / ``from autodiscovery_jobs.gcs import get_metadata``) keep working. New
code should import from :mod:`autodiscovery_jobs.persistence`.

Note that patching a name here does **not** affect callers that imported it from
``persistence`` — tests should target the real module.
"""

from __future__ import annotations

from .persistence import (
    PLACEHOLDER_NAME,
    ROOT_NODE_FILENAME,
    count_experiment_results,
    copy_job_data_files,
    create_job_directory,
    dataset_key,
    delete_job_directory,
    delete_shared_run_index,
    download_job_results,
    expire_datasets,
    generate_upload_url,
    get_job_args,
    get_job_path,
    get_job_results,
    get_metadata,
    get_shared_run_index,
    get_user_path,
    get_userid_for_job,
    has_data_files,
    job_exists,
    list_experiment_files,
    list_user_ids,
    list_user_jobs,
    parse_gcs_path,
    read_experiment_node,
    read_rich_outputs,
    soft_delete_job,
    upload_dataset,
    upload_job_args,
    upload_metadata,
    write_shared_run_index,
)

__all__ = [
    "PLACEHOLDER_NAME",
    "ROOT_NODE_FILENAME",
    "count_experiment_results",
    "copy_job_data_files",
    "create_job_directory",
    "dataset_key",
    "delete_job_directory",
    "delete_shared_run_index",
    "download_job_results",
    "expire_datasets",
    "generate_upload_url",
    "get_job_args",
    "get_job_path",
    "get_job_results",
    "get_metadata",
    "get_shared_run_index",
    "get_user_path",
    "get_userid_for_job",
    "has_data_files",
    "job_exists",
    "list_experiment_files",
    "list_user_ids",
    "list_user_jobs",
    "parse_gcs_path",
    "read_experiment_node",
    "read_rich_outputs",
    "soft_delete_job",
    "upload_dataset",
    "upload_job_args",
    "upload_metadata",
    "write_shared_run_index",
]
