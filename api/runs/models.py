from typing import Any
from pydantic import BaseModel, Field

class RunDetailsModel(BaseModel):
    """Model representing detailed information about a run"""

    execution_id: str | None = Field(None, description="Identifier for the execution")
    created_at: str = Field(..., description="Timestamp when the run was created")
    status: str = Field(..., description="Current status of the run")
    status_checked_at: str | None = Field(None, description="Timestamp when the status was last checked")

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
    status: str = Field(..., description="Current status of the experiment")
    is_surprising: bool | None = Field(
        ..., description="Flag indicating if the experiment is surprising"
    )
    surprise: float | None = Field(
        None, description="Numerical value representing the surprise level of the experiment"
    )
    prior: float | None = Field(None, description="Prior probability of the experiment")
    posterior: float | None = Field(None, description="Posterior probability of the experiment")
    runtime_ms: float | None = Field(None, description="Runtime of the experiment in milliseconds")
    hypothesis: str | None = Field(None, description="Hypothesis associated with the experiment")
    experiment_plan: dict[str, Any] | None = Field(None, description="Plan details of the experiment")
    review: str | None = Field(
        None, description="Results of the experiment in human-readable format"
    )
    code: str | None = Field(None, description="Code generated for the experiment")

class MetadataDatasetModel(BaseModel):
    """Model representing dataset metadata for a run"""

    name: str | None = Field(None, description="Filename of the dataset")
    description: str | None = Field(None, description="Description of the dataset")

class MetadataModel(BaseModel):
    """Model representing metadata for a run"""

    name: str | None = Field(None, description="Name of the run")
    description: str | None = Field(None, description="Description of the run")
    datasets: list[MetadataDatasetModel] | None = Field(
        None, description="List of datasets associated with the run"
    )

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "MetadataModel":
        """Create MetadataModel from a dictionary"""
        datasets_data = data.get("datasets", [])
        datasets = [
            MetadataDatasetModel(
                name=ds.get("name"),
                description=ds.get("description"),
            )
            for ds in datasets_data
        ]
        return MetadataModel(
            name=data.get("name"),
            description=data.get("description"),
            datasets=datasets,
        )

class RunModel(BaseModel):
    """Model representing a run with its attributes"""

    runid: str = Field(..., description="Unique identifier for the run")
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
    execution_status: dict[str, Any] | None = Field(
        None, description="Execution status of the run"
    )
    run_metadata: MetadataModel | None = Field(
        None, description="Metadata associated with the run"
    )

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

class GetExampleRunsRequestModel(BaseModel):
    """Model for the request to get example runs"""

    limit: int = Field(..., description="Maximum number of example runs to retrieve")

class GetExampleRunsResponseModel(BaseModel):
    """Model for the response containing a list of example runs"""

    runs: list[RunModel] = Field(..., description="List of example runs")

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
