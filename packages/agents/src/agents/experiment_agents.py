"""Experiment-oriented agents and workflow orchestration."""

from __future__ import annotations

from typing import AsyncGenerator

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.code_executors import BuiltInCodeExecutor
from google.adk.events import Event
from typing_extensions import override

DEFAULT_MODEL = "gemini-2.0-flash"

experiment_generator = LlmAgent(
    name="experiment_generator",
    model=DEFAULT_MODEL,
    description="Generates the final experiment summary and next steps.",
    instruction=(
        "You are an experiment generator that prepares the final narrative.\n"
        "Use the user request, the experiment code, and any analysis/review notes.\n"
        "Experiment code:\n{experiment_code?}\n\n"
        "Analysis notes:\n{analysis_feedback?}\n\n"
        "Review notes:\n{review_feedback?}\n\n"
        "Revision guidance:\n{revision_instructions?}\n\n"
        "Provide a concise final summary and recommended next steps."
    ),
    output_key="experiment_summary",
)

experiment_programmer = LlmAgent(
    name="experiment_programmer",
    model=DEFAULT_MODEL,
    description="Writes or updates experiment code based on the request.",
    instruction=(
        "You are an experiment programmer. Write Python code that implements the user's"
        " experiment. Incorporate any revision guidance if present.\n"
        "Revision guidance:\n{revision_instructions?}\n\n"
        "Prior analysis feedback:\n{analysis_feedback?}\n\n"
        "Return only the Python code with no surrounding markdown."
    ),
    output_key="experiment_code",
)

code_executor = LlmAgent(
    name="code_executor",
    model=DEFAULT_MODEL,
    description="Executes experiment code and summarizes the results.",
    instruction=(
        "You are a code execution agent. Run the Python code provided below using a"
        " python code block. After execution, summarize the key outputs and results in"
        " plain text.\n\n"
        "Experiment code:\n{experiment_code}\n"
    ),
    code_executor=BuiltInCodeExecutor(),
    output_key="execution_summary",
)

experiment_analyst = LlmAgent(
    name="experiment_analyst",
    model=DEFAULT_MODEL,
    description="Evaluates execution results for correctness and issues.",
    instruction=(
        "You are an experiment analyst. Review the execution summary and decide if the"
        " experiment succeeded.\n\n"
        "Execution summary:\n{execution_summary?}\n\n"
        "Respond with 'pass: <reason>' if results are acceptable or 'fail: <reason>' if"
        " they are not."
    ),
    output_key="analysis_feedback",
)

experiment_reviewer = LlmAgent(
    name="experiment_reviewer",
    model=DEFAULT_MODEL,
    description="Reviews the experiment design and analysis for quality.",
    instruction=(
        "You are an experiment reviewer. Evaluate the experiment design and results.\n\n"
        "Experiment code:\n{experiment_code?}\n\n"
        "Analysis feedback:\n{analysis_feedback?}\n\n"
        "Respond with 'pass: <reason>' if the experiment is acceptable or 'fail: <reason>'"
        " if it needs revision."
    ),
    output_key="review_feedback",
)

experiment_reviser = LlmAgent(
    name="experiment_reviser",
    model=DEFAULT_MODEL,
    description="Produces revision guidance when the review fails.",
    instruction=(
        "You are an experiment reviser. Provide concrete, actionable revision guidance"
        " to address the review feedback.\n\n"
        "Review feedback:\n{review_feedback?}\n\n"
        "Return concise revision instructions."
    ),
    output_key="revision_instructions",
)


class ExperimentWorkflowAgent(BaseAgent):
    """Custom workflow agent orchestrating experiment iterations."""

    experiment_generator: LlmAgent
    experiment_programmer: LlmAgent
    experiment_analyst: LlmAgent
    experiment_reviewer: LlmAgent
    experiment_reviser: LlmAgent
    code_executor: LlmAgent

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        *,
        name: str,
        experiment_generator: LlmAgent,
        experiment_programmer: LlmAgent,
        experiment_analyst: LlmAgent,
        experiment_reviewer: LlmAgent,
        experiment_reviser: LlmAgent,
        code_executor: LlmAgent,
        max_programmer_attempts: int = 6,
    ) -> None:
        """Initialize the experiment workflow agent.

        Args:
            name: The agent name.
            experiment_generator: Generates the final experiment summary.
            experiment_programmer: Produces experiment code.
            experiment_analyst: Validates execution results.
            experiment_reviewer: Reviews the experiment quality.
            experiment_reviser: Provides revision guidance after review failure.
            code_executor: Runs experiment code and summarizes output.
            max_programmer_attempts: Maximum programmer retries after analysis failure.
        """
        self._max_programmer_attempts = max_programmer_attempts
        super().__init__(
            name=name,
            description=(
                "Orchestrates programming, execution, analysis, review, revision, and"
                " generation for experiments."
            ),
            experiment_generator=experiment_generator,
            experiment_programmer=experiment_programmer,
            experiment_analyst=experiment_analyst,
            experiment_reviewer=experiment_reviewer,
            experiment_reviser=experiment_reviser,
            code_executor=code_executor,
            sub_agents=[
                experiment_programmer,
                code_executor,
                experiment_analyst,
                experiment_reviewer,
                experiment_reviser,
                experiment_generator,
            ],
        )

    @override
    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Run the experiment workflow with retries and review handling."""
        analysis_passed = False

        for attempt in range(1, self._max_programmer_attempts + 1):
            async for event in self.experiment_programmer.run_async(ctx):
                yield event

            async for event in self.code_executor.run_async(ctx):
                yield event

            async for event in self.experiment_analyst.run_async(ctx):
                yield event

            analysis_feedback = str(ctx.session.state.get("analysis_feedback", ""))
            analysis_passed = self._is_passing_result(analysis_feedback)
            ctx.session.state["analysis_passed"] = analysis_passed

            if analysis_passed:
                break

            if attempt == self._max_programmer_attempts:
                break

        async for event in self.experiment_reviewer.run_async(ctx):
            yield event

        review_feedback = str(ctx.session.state.get("review_feedback", ""))
        review_passed = self._is_passing_result(review_feedback)
        ctx.session.state["review_passed"] = review_passed

        if not review_passed:
            async for event in self.experiment_reviser.run_async(ctx):
                yield event

            async for event in self.experiment_programmer.run_async(ctx):
                yield event

        async for event in self.experiment_generator.run_async(ctx):
            yield event

    def _is_passing_result(self, feedback: str) -> bool:
        """Determine whether the feedback indicates a passing result."""
        # Normalize verdict parsing to avoid false negatives.
        normalized = feedback.strip().lower()
        if normalized.startswith("pass"):
            return True
        if normalized.startswith("fail"):
            return False
        return "pass" in normalized and "fail" not in normalized


experiment_workflow_agent = ExperimentWorkflowAgent(
    name="experiment_workflow_agent",
    experiment_generator=experiment_generator,
    experiment_programmer=experiment_programmer,
    experiment_analyst=experiment_analyst,
    experiment_reviewer=experiment_reviewer,
    experiment_reviser=experiment_reviser,
    code_executor=code_executor,
)
