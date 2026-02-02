from __future__ import annotations

from typing import Any

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
            )
            for ds in datasets_data
        ]
        return MetadataModel(
            name=data.get("name"),
            description=data.get("description"),
            domain=data.get("domain"),
            intent=data.get("intent"),
            datasets=datasets,
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


class GetRunExperimentsResponseModel(BaseModel):
    """Model for the response containing a list of experiments within a run"""

    runid: str = Field(..., description="Identifier of the run")
    after_experiment_id: str | None = Field(
        None, description="Experiment ID after which experiments are fetched"
    )
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
