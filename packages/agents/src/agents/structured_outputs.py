"""Structured outputs for experiment agents."""

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator


class StrictBaseModel(BaseModel):
    """Base model enforcing strict schemas for LLM structured outputs."""

    model_config = ConfigDict(extra="forbid")


class Relationship(StrictBaseModel):
    """Represents a relationship between two variables in a hypothesis.

    Attributes:
        explanatory: The independent/explanatory variable in the relationship.
        response: The dependent/response variable in the relationship.
        relationship: Description of how the explanatory variable affects the response.
    """

    explanatory: str
    response: str
    relationship: str


class HypothesisDimensions(StrictBaseModel):
    """Structured representation of the key dimensions of a hypothesis.

    Attributes:
        contexts: Boundary conditions and assumptions for the hypothesis.
        variables: Key concepts/variables involved in the hypothesis.
        relationships: Causal relationships between variable pairs.
    """

    contexts: list[str]
    variables: list[str]
    relationships: list[Relationship]


class Hypothesis(StrictBaseModel):
    """A falsifiable hypothesis supported by structured dimensions.

    Attributes:
        hypothesis: The hypothesis statement.
        dimensions: Structured dimensions of the hypothesis.
    """

    hypothesis: str
    dimensions: HypothesisDimensions


class ExperimentPlan(StrictBaseModel):
    """Represents the experiment plan with a title, objective, steps, and deliverables.

    Attributes:
        objective: The main goal or objective of the experiment.
        steps: Steps to be followed to implement the experiment.
        deliverables: Expected outcomes or deliverables from the experiment.
    """

    objective: str
    steps: str
    deliverables: str


class Experiment(StrictBaseModel):
    """Represents an experiment with a hypothesis and plan.

    Attributes:
        hypothesis: A natural-language hypothesis about the world.
        experiment_plan: The structured experiment plan.
    """

    hypothesis: str
    experiment_plan: ExperimentPlan


class ExperimentHypothesis(StrictBaseModel):
    """Represents an experiment hypothesis and its plan.

    Attributes:
        experiment_plan: A structured experiment plan to verify a hypothesis.
        hypothesis: A natural-language hypothesis statement.
    """

    experiment_plan: ExperimentPlan
    hypothesis: str


class ExperimentList(StrictBaseModel):
    """A collection of experiments.

    Attributes:
        experiments: List of Experiment objects.
    """

    experiments: list[Experiment]


class ExperimentHypothesisList(StrictBaseModel):
    """A collection of experiment hypotheses.

    Attributes:
        experiments: List of ExperimentHypothesis objects.
    """

    experiments: list[ExperimentHypothesis]


class ExperimentCode(StrictBaseModel):
    """Contains the code implementation for an experiment.

    Attributes:
        code: The code to be executed for the experiment.
    """

    code: str


class ProgramCritique(StrictBaseModel):
    """Feedback on experiment code implementation.

    Attributes:
        fixes: List of suggested fixes or improvements for the code.
    """

    fixes: list[str]


class ExperimentAnalyst(StrictBaseModel):
    """Analysis of experiment results.

    Attributes:
        analysis: Detailed analysis of the experiment outcomes.
        success: Whether the experiment was successful.
    """

    analysis: str
    success: bool

    @model_validator(mode="after")
    def analysis_required_on_success(self) -> Self:
        """Require analysis when success is True."""
        if self.success and self.analysis is None:
            raise ValueError("analysis is required when success is True")
        return self


class ExperimentReviewer(StrictBaseModel):
    """Review of an experiment's execution and results.

    Attributes:
        feedback: Feedback when experiment fails.
        success: Whether the experiment was successful.
    """

    feedback: str
    success: bool

    @model_validator(mode="after")
    def feedback_required_on_failure(self) -> Self:
        """Require feedback when success is False."""
        if not self.success and self.feedback is None:
            raise ValueError("feedback is required when success is False")
        return self


class ImageAnalysis(StrictBaseModel):
    """Structured representation of plot axes and analysis information.

    Attributes:
        plot_type: The plot type.
        title: The title of the plot.
        x_axis_label: Label for the x-axis.
        y_axis_label: Label for the y-axis.
        x_axis_range: Range of values on the x-axis.
        y_axis_range: Range of values on the y-axis.
        data_trends: Observed trends in the data.
        statistical_insights: Statistical observations and metrics.
        annotations_and_legends: Plot annotations and legend descriptions.
    """

    plot_type: str
    title: str
    x_axis_label: str
    y_axis_label: str
    x_axis_range: list[int] | list[float]
    y_axis_range: list[int] | list[float]
    data_trends: list[str]
    statistical_insights: list[str]
    annotations_and_legends: list[str]


class ExecutionResult(StrictBaseModel):
    """Execution output for code runs."""

    exit_code: int
    result: str
