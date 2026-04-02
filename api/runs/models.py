from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


class RunDetailsModel(BaseModel):
    """Model representing detailed information about a run"""

    execution_id: str | None = Field(None, description="Identifier for the execution")
    created_at: str = Field(..., description="Timestamp when the run was created")
    status: str = Field(..., description="Current status of the run")
    status_checked_at: str | None = Field(
        None, description="Timestamp when the status was last checked"
    )
    finished_at: str | None = Field(
        None, description="Timestamp when the run finished (terminal status)"
    )


class RunStatsModel(BaseModel):
    """Model representing statistics of a run"""

    requested_experiments: int = Field(..., description="Total number of experiments requested")
    completed_experiments: int = Field(
        ..., description="Number of experiments that have been completed"
    )
    pending_experiments: int = Field(
        ..., description="Number of experiments that are still pending"
    )
    num_surprising_experiments: int = Field(
        ..., description="Number of experiments that are considered surprising"
    )


class ExperimentModel(BaseModel):
    """Model representing an experiment with its attributes"""

    experiment_id: str = Field(..., description="Unique identifier for the experiment")
    parent_id: str | None = Field(None, description="Identifier of the parent experiment, if any")
    child_ids: list[str] | None = Field(
        None, description="Identifiers of the child experiments, if any"
    )
    creation_idx: int = Field(
        ..., description="Index representing the creation order of the experiment"
    )
    created_at: str | None = Field(
        None, description="ISO timestamp when the experiment was created"
    )
    id_in_run: int | None = Field(
        None,
        description="Unique identifier for the experiment relative to the run, based on its order",
    )
    status: str = Field(..., description="Current status of the experiment")
    is_surprising: bool | None = Field(
        ..., description="Flag indicating if the experiment is surprising"
    )
    surprise: float | None = Field(
        None, description="Numerical value representing the surprise level of the experiment"
    )
    prior: float | None = Field(None, description="Prior probability of the experiment")
    posterior: float | None = Field(None, description="Posterior probability of the experiment")
    prior_belief: dict[str, Any] | None = Field(
        None, description="Full prior belief payload for the experiment"
    )
    posterior_belief: dict[str, Any] | None = Field(
        None, description="Full posterior belief payload for the experiment"
    )
    runtime_ms: float | None = Field(None, description="Runtime of the experiment in milliseconds")
    hypothesis: str | None = Field(None, description="Hypothesis associated with the experiment")
    analysis: str | None = Field(None, description="Analysis details of the experiment")
    experiment_plan: dict[str, Any] | None = Field(
        None, description="Plan details of the experiment"
    )
    review: str | None = Field(
        None, description="Results of the experiment in human-readable format"
    )
    code: str | None = Field(None, description="Code generated for the experiment")
    code_output: str | None = Field(
        None, description="Raw output from the code executor for the experiment"
    )
    rich_outputs: list[dict[str, Any]] | None = Field(
        None, description="Rich output bundles generated during code execution"
    )

    @model_validator(mode="after")
    def set_id_in_run(self) -> ExperimentModel:
        """Set a stable experiment identifier based on creation order.

        Returns:
            ExperimentModel: The updated model with a populated id_in_run.
        """
        if self.id_in_run is None:
            self.id_in_run = self.creation_idx - 1
        return self


class MetadataDatasetModel(BaseModel):
    """Model representing dataset metadata for a run"""

    name: str | None = Field(None, description="Filename of the dataset")
    description: str | None = Field(None, description="Description of the dataset")
    content_type: str | None = Field(None, description="MIME type of the dataset file")
    file_size_bytes: int | None = Field(None, description="Size of the file in bytes")
    url: Optional[str] = None
    is_preloaded: bool = Field(False, description="Whether this is a preloaded dataset")


class RunArgsModel(BaseModel):
    """Model representing run arguments/configuration"""

    n_experiments: int | None = Field(None, description="Number of experiments to run")
    exploration_weight: float | None = Field(None, description="Weight for exploration in MCTS")
    mcts_selection: str | None = Field(None, description="MCTS selection strategy")
    surprisal_width: float | None = Field(None, description="Surprisal threshold width")
    evidence_weight: float | None = Field(None, description="Weight for evidence in belief updates")
    warmstart_experiments: str | None = Field(None, description="Path to warmstart experiments")
    n_warmstart: int | None = Field(None, description="Number of warmstart experiments")

    @staticmethod
    def from_dict(data: dict[str, Any]) -> RunArgsModel:
        """Create RunArgsModel from a dictionary"""
        return RunArgsModel(
            n_experiments=data.get("n_experiments"),
            exploration_weight=data.get("exploration_weight"),
            mcts_selection=data.get("mcts_selection"),
            surprisal_width=data.get("surprisal_width"),
            evidence_weight=data.get("evidence_weight"),
            warmstart_experiments=data.get("warmstart_experiments"),
            n_warmstart=data.get("n_warmstart"),
        )


class MetadataModel(BaseModel):
    """Model representing metadata for a run.

    This includes both descriptive metadata and job configuration parameters.
    """

    # Descriptive metadata
    name: str | None = Field(None, description="Name of the run")
    description: str | None = Field(None, description="Description of the run")
    domain: str | None = Field(None, description="Domain of the run")
    intent: str | None = Field(None, description="High-level intent for the run")
    datasets: list[MetadataDatasetModel] | None = Field(
        None, description="List of datasets associated with the run"
    )

    # Bookmarking
    is_bookmarked: bool | None = Field(
        None, description="Whether the run is bookmarked (marked as interesting by the user)"
    )
    bookmarked_experiment_ids: list[str] | None = Field(
        None, description="List of experiment IDs bookmarked by the user"
    )

    # Sharing
    is_shared: bool | None = Field(
        None, description="Whether the run is shared (viewable by anyone). Missing means not shared."
    )

    # Job configuration parameters
    n_experiments: int | None = Field(None, description="Number of experiments to run")
    exploration_weight: float | None = Field(None, description="Weight for exploration in MCTS")
    mcts_selection: str | None = Field(None, description="MCTS selection strategy")
    surprisal_width: float | None = Field(None, description="Surprisal threshold width")
    evidence_weight: float | None = Field(None, description="Weight for evidence in belief updates")
    warmstart_experiments: str | None = Field(None, description="Path to warmstart experiments")
    n_warmstart: int | None = Field(None, description="Number of warmstart experiments")

    @staticmethod
    def from_dict(data: dict[str, Any]) -> MetadataModel:
        """Create MetadataModel from a dictionary"""
        datasets_data = data.get("datasets", [])
        datasets = [
            MetadataDatasetModel(
                name=ds.get("name"),
                description=ds.get("description"),
                content_type=ds.get("content_type"),
                file_size_bytes=ds.get("file_size_bytes"),
                url=ds.get("url", None),
                is_preloaded=ds.get("is_preloaded", False)

            )
            for ds in datasets_data
        ]
        return MetadataModel(
            name=data.get("name"),
            description=data.get("description"),
            domain=data.get("domain"),
            intent=data.get("intent"),
            datasets=datasets,
            is_shared=data.get("is_shared"),
            is_bookmarked=data.get("is_bookmarked"),
            bookmarked_experiment_ids=data.get("bookmarked_experiment_ids"),
            n_experiments=data.get("n_experiments"),
            exploration_weight=data.get("exploration_weight"),
            mcts_selection=data.get("mcts_selection"),
            surprisal_width=data.get("surprisal_width"),
            evidence_weight=data.get("evidence_weight"),
            warmstart_experiments=data.get("warmstart_experiments"),
            n_warmstart=data.get("n_warmstart"),
        )


class RunModel(BaseModel):
    """Model representing a run with its attributes"""

    runid: str = Field(..., description="Unique identifier for the run")
    userid: str = Field(..., description="User identifier who owns the run")
    status: str = Field(..., description="Current status of the run")
    name: str | None = Field(None, description="Name of the run")
    description: str | None = Field(None, description="Description of the run")
    path: str | None = Field(None, description="Filesystem path of the run")
    run_details: RunDetailsModel | None = Field(
        None, description="Detailed information about the run"
    )
    run_stats: RunStatsModel | None = Field(
        None, description="Statistical information about the run"
    )
    execution_status: dict[str, Any] | None = Field(None, description="Execution status of the run")
    run_metadata: MetadataModel | None = Field(None, description="Metadata associated with the run")
    max_file_size: str | None = Field(None, description="Maximum file size limit for uploads, if applicable")
    can_view_datasets: bool = Field(False, description="Bool flag determining if AI1 datasets are visible")


class GetRunMetadataRequestModel(BaseModel):
    """Model for the request to get run metadata"""

    runid: str = Field(..., description="Identifier of the run to fetch metadata for")
    userid: str | None = Field(
        None, description="User identifier for whom to retrieve metadata; defaults to the viewer"
    )


class GetRunMetadataResponseModel(BaseModel):
    """Model for the response containing run metadata"""

    runid: str = Field(..., description="Identifier of the run")
    metadata: MetadataModel = Field(..., description="Metadata associated with the run")


class GetViewerRunsRequestModel(BaseModel):
    """Model for the request to get runs for the viewer"""

    limit: int = Field(..., description="Maximum number of runs to retrieve")
    userid: str = Field(
        ..., description="User identifier for whom to retrieve runs; defaults to the viewer"
    )


class GetViewerRunsResponseModel(BaseModel):
    """Model for the response containing a list of runs for the viewer"""

    runs: list[RunModel] = Field(..., description="List of runs available to the viewer")


class GetRunExperimentsRequestModel(BaseModel):
    """Model for the request to get experiments within a run"""

    known_experiment_ids: list[str] = Field(
        default_factory=list,
        description="List of experiment IDs the client already has"
    )


class GetRunExperimentsResponseModel(BaseModel):
    """Model for the response containing a list of experiments within a run"""

    runid: str = Field(..., description="Identifier of the run")
    has_job_completed: bool = Field(
        ..., description="Flag indicating if the job has completed, polling can stop"
    )
    experiments: list[ExperimentModel] = Field(..., description="List of experiments in the run")


class GetExperimentStatusResponseModel(BaseModel):
    """Model for the response containing experiment status and related info"""

    runid: str | None = Field(None, description="Identifier of the run containing the experiment")
    experiment_id: str = Field(..., description="Unique identifier for the experiment")
    experiment: ExperimentModel | None = Field(..., description="Details of the experiment")


class GenerateUploadUrlRequestModel(BaseModel):
    """Model for the request to generate a presigned upload URL"""

    runid: str = Field(
        ..., description="Identifier of the run for which to generate the upload URL"
    )
    userid: str = Field(..., description="User identifier for whom to generate the upload URL")
    filename: str = Field(..., description="Name of the file to upload")
    content_type: str = Field(..., description="MIME type of the file")
    file_size_bytes: int = Field(..., description="Size of the file in bytes")


class GenerateUploadUrlResponseModel(BaseModel):
    """Model for the response containing the presigned upload URL"""

    upload_url: str = Field(..., description="Presigned URL for uploading the file to GCS")
    gcs_path: str = Field(..., description="GCS path where file will be stored")
    filename: str = Field(..., description="Name of the file")
    expires_at_unix: int = Field(
        ..., description="Unix timestamp (seconds since epoch) when the URL expires"
    )


class CreateRunResponseModel(BaseModel):
    """Model for the response when creating a new run"""

    runid: str = Field(..., description="Unique identifier for the newly created run")
    path: str = Field(..., description="GCS path where the run is stored")
    message: str = Field(..., description="Success message")
    run_details: RunDetailsModel = Field(..., description="Initial run details")
    max_file_size: str | None = Field(None, description="Maximum file size limit for uploads, if applicable")


class GetRunRequestModel(BaseModel):
    """Model for the request to get a specific run"""

    runid: str = Field(..., description="Identifier of the run to retrieve")
    userid: str = Field(..., description="User identifier who owns the run or public user")


class DeleteRunRequestModel(BaseModel):
    """Model for the request to delete a run"""

    runid: str = Field(..., description="Identifier of the run to delete")
    userid: str = Field(..., description="User identifier who owns the run")


class DeleteRunResponseModel(BaseModel):
    """Model for the response when deleting a run"""

    message: str = Field(..., description="Success message")
    deleted_files_count: int = Field(
        ..., description="Number of files deleted from data/ directory"
    )
    preserved_files_count: int = Field(
        ..., description="Number of files preserved (metadata, outputs)"
    )
    status: str = Field(..., description="Updated status of the run (DELETED)")
    deleted_at: str = Field(..., description="ISO timestamp when the run was deleted")
    cancelled_execution: bool = Field(
        ...,
        description="Whether the Cloud Run execution was cancelled (true if job was running)",
    )


class UploadDatasetResponseModel(BaseModel):
    """Model for the response when uploading a dataset"""

    path: str = Field(..., description="GCS path where the dataset was stored")
    filename: str = Field(..., description="Name of the uploaded file")
    message: str = Field(..., description="Success message")


class SaveMetadataRequestModel(BaseModel):
    """Model for the request to save or update run metadata"""

    runid: str = Field(..., description="Identifier of the run to save metadata for")
    userid: str = Field(..., description="User identifier who owns the run")
    metadata: MetadataModel = Field(..., description="Metadata to save for the run")


class SaveMetadataResponseModel(BaseModel):
    """Model for the response when saving metadata"""

    path: str = Field(..., description="GCS path where the metadata was stored")
    message: str = Field(..., description="Success message")


class SubmitRunRequestModel(BaseModel):
    """Model for the request to submit a run for execution"""

    runid: str = Field(..., description="Identifier of the run to submit")
    userid: str = Field(..., description="User identifier who owns the run")


class SubmitRunResponseModel(BaseModel):
    """Model for the response when submitting a run"""

    execution_id: str = Field(..., description="Cloud Run execution identifier")
    message: str = Field(..., description="Success message")
    run_details: RunDetailsModel = Field(
        ..., description="Updated run details including execution_id"
    )


class GetRunStatusRequestModel(BaseModel):
    """Model for the request to get run status"""

    runid: str = Field(..., description="Identifier of the run to check status for")
    userid: str = Field(..., description="User identifier who owns the run or public user")


class GetRunStatusResponseModel(BaseModel):
    """Model for the response containing run status"""

    runid: str = Field(..., description="Identifier of the run")
    run_details: RunDetailsModel = Field(..., description="Detailed run status information")
    execution_status: dict[str, Any] | None = Field(
        None, description="Detailed Cloud Run execution status (if execution_id exists)"
    )


class CancelRunRequestModel(BaseModel):
    """Model for the request to cancel a running job"""

    runid: str = Field(..., description="Identifier of the run to cancel")
    userid: str = Field(..., description="User identifier who owns the run")


class CancelRunResponseModel(BaseModel):
    """Model for the response when cancelling a run"""

    message: str = Field(..., description="Success message confirming cancellation")

class BookmarkRunRequestModel(BaseModel):
    """Model for the request to bookmark or unbookmark a run"""

    runid: str = Field(..., description="Identifier of the run to bookmark/unbookmark")
    userid: str = Field(..., description="User identifier who owns the run")
    is_bookmarked: bool = Field(..., description="Whether to bookmark (true) or unbookmark (false) the run")

class BookmarkRunResponseModel(BaseModel):
    """Model for the response when bookmarking/unbookmarking a run"""

    is_bookmarked: bool = Field(..., description="Updated bookmarked status")
    message: str = Field(..., description="Success message")


class BookmarkExperimentRequestModel(BaseModel):
    """Model for the request to bookmark or unbookmark an experiment"""

    runid: str = Field(..., description="Identifier of the run containing the experiment")
    userid: str = Field(..., description="User identifier who owns the run")
    experiment_id: str = Field(..., description="Identifier of the experiment to bookmark/unbookmark")
    is_bookmarked: bool = Field(..., description="Whether to bookmark (true) or unbookmark (false) the experiment")


class BookmarkExperimentResponseModel(BaseModel):
    """Model for the response when bookmarking/unbookmarking an experiment"""

    experiment_id: str = Field(..., description="Identifier of the experiment")
    is_bookmarked: bool = Field(..., description="Updated bookmarked status")


class ShareRunRequestModel(BaseModel):
    """Model for the request to share or unshare a run"""

    runid: str = Field(..., description="Identifier of the run to share/unshare")
    userid: str = Field(..., description="User identifier who owns the run")
    is_shared: bool = Field(..., description="Whether to share (true) or unshare (false) the run")


class ShareRunResponseModel(BaseModel):
    """Model for the response when sharing/unsharing a run"""

    is_shared: bool = Field(..., description="Updated sharing status")
    message: str = Field(..., description="Success message")


class GetSharedRunOwnerRequestModel(BaseModel):
    """Request model for getting a shared run's owner"""

    runid: str = Field(..., description="Identifier of the shared run")


class GetSharedRunOwnerResponseModel(BaseModel):
    """Response model containing a shared run's owner"""

    runid: str = Field(..., description="Identifier of the run")
    userid: str = Field(..., description="User ID of the run owner")

MetadataDatasetModel.model_rebuild()
MetadataModel.model_rebuild()
RunModel.model_rebuild()