from pydantic import BaseModel, Field


class ExperimentSummaryModel(BaseModel):
    """Model representing a summary of an experiment"""

    experiment_id: str = Field(..., description="Unique identifier for the experiment")
    parent_id: str | None = Field(None, description="Identifier of the parent experiment, if any")
    child_ids: list[str] | None = Field(
        None, description="Identifiers of the child experiments, if any"
    )
    status: str = Field(..., description="Current status of the experiment")
    is_surprising: bool | None = Field(
        ..., description="Flag indicating if the experiment is surprising"
    )


class ExperimentDetailedModel(BaseModel):
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
    runtime_ms: float | None = Field(None, description="Runtime of the experiment in milliseconds")
    hypothesis: str | None = Field(None, description="Hypothesis associated with the experiment")
    experiment_plan: dict | None = Field(None, description="Plan details of the experiment")
    review: str | None = Field(
        None, description="Results of the experiment in human-readable format"
    )

    def to_summary(self) -> ExperimentSummaryModel:
        """Convert to ExperimentSummaryModel for API response.

        Returns:
            ExperimentSummaryModel instance
        """
        return ExperimentSummaryModel(
            experiment_id=self.experiment_id,
            parent_id=self.parent_id,
            child_ids=self.child_ids,
            status=self.status,
            is_surprising=self.is_surprising,
        )


class GetRunExperimentsResponseModel(BaseModel):
    """Model for the response containing a list of experiments within a run"""

    runid: str = Field(..., description="Identifier of the run")
    after_experiment_id: str | None = Field(
        None, description="Experiment ID after which experiments are fetched"
    )
    experiments: list[ExperimentSummaryModel] = Field(
        ..., description="List of experiments in the run"
    )


class GetExperimentStatusResponseModel(BaseModel):
    """Model for the response containing experiment status and related info"""

    runid: str | None = Field(None, description="Identifier of the run containing the experiment")
    experiment_id: str = Field(..., description="Unique identifier for the experiment")
    experiment: ExperimentDetailedModel | None = Field(..., description="Details of the experiment")
