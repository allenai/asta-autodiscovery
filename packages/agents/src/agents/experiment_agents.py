"""Experiment-oriented agents and workflow orchestration."""

from __future__ import annotations

import json
import os
import textwrap
from collections.abc import AsyncGenerator
from typing import Any, Literal, Protocol, cast, override

from asta_sandbox import ExecutionResult, InProcessExecutor, SandboxExecutor
from asta_sandbox.backends.modal_ephemeral import ModalEphemeralExecutor
from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.models.lite_llm import LiteLlm
from google.genai import types
from pydantic import BaseModel

from .structured_outputs import (
    Experiment,
    ExperimentAnalyst,
    ExperimentCode,
    ExperimentList,
    ExperimentReviewer,
)

MODEL_ENV_VAR = "ASTA_AGENTS_MODEL"
DEFAULT_MODEL: LiteLlm = LiteLlm(model=os.getenv(MODEL_ENV_VAR, "openai/gpt-5-mini"))
ExecutionBackend = Literal["local", "modal"]

_DEFAULT_MODAL_APP_NAME = "autodiscovery"

INSTALL_SNIPPET = "%pip install package1 package2"

ALTERNATIVE_INSTALL_SNIPPET = textwrap.dedent("""
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "package1", "package2"],
        check=True,
    )
""").strip()


def create_experiment_agents(*, model: LiteLlm | None = None) -> dict[str, LlmAgent]:
    """Create experiment LLM agents configured with the provided model.

    Args:
        model: LiteLLM model instance. Defaults to the configured package default.

    Returns:
        Dictionary of named LLM agents for the experiment workflow.
    """
    resolved_model = model or DEFAULT_MODEL
    if not isinstance(resolved_model, LiteLlm):
        raise TypeError("Experiment agents require a LiteLlm instance for the model configuration.")
    experiment_generator = LlmAgent(
        name="experiment_generator",
        model=resolved_model,
        description="Generates the final experiment summary and next steps.",
        instruction=(
            "You are a research scientist who is interested in doing open-ended, data-driven "
            "research using the provided dataset(s). "
            "{user_query?}\n\n"
            "Be creative and think of new and interesting verifiable hypotheses and "
            "corresponding experiments. The hypothesis should be a falsifiable statement "
            "that can be sufficiently tested by an experiment using the provided data. "
            "Explain in natural language what this experiment plan is so that a programmer "
            "can implement it (do not provide the code yourself). Remember, you are "
            "interested in open-ended research, so your proposals may be exploratory in "
            "nature and may have only an indirect connection to the previous explorations "
            "provided. Here are some instructions that you must follow:\n"
            "1. Strictly use only the dataset(s) provided and do not simulate dummy/synthetic "
            "data or columns that cannot be derived from the existing columns.\n"
            "2. Each hypothesis (and experiment plan) should be creative, independent, and "
            "self-contained.\n"
            "3. Use the prior experiments/hypotheses as inspiration to think of interesting "
            "and creative new experiments/hypotheses. However, do not repeat the same "
            "experiments/hypotheses.\n\n"
            "Here is a possible approach to coming up with a new hypothesis and experiment "
            "plan:\n"
            "1. Find an interesting context: this could be a specific subset of the data. "
            "E.g., if the dataset has multiple categorical variables, you could split the "
            "data based on specific values of such variables, which would then allow you to "
            "validate a hypothesis in the specific contexts defined by the values of those "
            "variables.\n"
            "2. Find interesting variables: these could be the columns in the dataset that "
            "you find interesting or relevant to the context. You are allowed and encouraged "
            "to create composite variables derived from the existing variables.\n"
            "3. Find interesting relationships: these are interactions between the variables "
            "that you find interesting or relevant to the context. You are encouraged to "
            "propose experiments involving complex predictive or causal models.\n"
            "4. You must require that your proposed hypotheses are verifiable using robust "
            "statistical tests. Remember, your programmer can install python packages via "
            "pip which can allow it to write code for complex statistical analyses.\n"
            "5. Multiple datasets: If you are provided with more than one dataset, then try "
            "to also propose hypotheses that utilize contexts, variables, and relationships "
            "across datasets, e.g., this may involve using join or similar operations.\n\n"
            "Generally, in typical data-driven research, you will need to explore and "
            "visualize the data for possible high-level insights, clean, transform, or derive "
            "new variables from the dataset to be suited for the investigation, deep-dive into "
            "specific parts of the data for fine-grained analysis, perform data modeling, and "
            "run statistical tests. Now, generate exactly {branching_factor?} new hypotheses "
            "with their experiment plans."
        ),
        output_key="experiment_list",
        output_schema=ExperimentList,
    )

    experiment_programmer = LlmAgent(
        name="experiment_programmer",
        model=resolved_model,
        description="Writes or updates experiment code based on the request.",
        instruction=(
            "You are a scientific experiment programmer proficient in writing python code "
            "given an experiment plan. Your code will be included in a python file that is "
            "executed and any relevant results should be printed to standard out or presented "
            "using plt.show appropriately. Make sure you provide python code in the proper "
            "format to execute. Ensure your code is clean and concise, and include debug "
            "statements only when they are absolutely necessary. Use only the dataset given "
            "and do not assume any other files are available. The state is not preserved "
            "between code blocks, so do not assume any variables or imports from previous "
            "code blocks. Import any libraries you need to use. Always attempt to import a "
            "library before installing it (it may already be installed). If you need to "
            "install a library, use the following code example at the start of your code:"
            f"{INSTALL_SNIPPET}\n"
            "or use this alternative approach if necessary:\n"
            f"{ALTERNATIVE_INSTALL_SNIPPET}\n"
            "Prefer using installed libraries over installing new libraries whenever "
            "possible. If possible, instead of downgrading library versions, try to adapt "
            "your code to work with a more updated version that is already installed. Never "
            "attempt to create a new environment. Always use the current environment. If the "
            "code requires generating plots, use plt.show (not plt.savefig). Avoid printing "
            "the whole data structure to the console directly if it is large; instead, print "
            "concise results that are directly relevant to the experiment. You are allowed 6 "
            "total attempts to run the code, including debugging attempts.\n\n"
            "Debugging instructions:\n"
            "1. Only debug if you are either unsure about the executability or validity of "
            "the code (i.e., whether it satisfies the proposed experiment).\n"
            "2. If the code you are writing is intended for debugging, the first line of your "
            'code must be "# [debug]" only.\n'
            '3. DO NOT use "[debug]" anywhere else in your code.\n'
            "4. DO NOT combine any debug code and the actual experiment implementation code; "
            "keep them separate.\n"
            "5. For each experiment, you are allowed to debug at most 3 times.\n"
            "6. As much as possible, minimize the number of debugging steps you use."
        ),
        output_key="experiment_code_payload",
        output_schema=ExperimentCode,
    )

    experiment_analyst = LlmAgent(
        name="experiment_analyst",
        model=resolved_model,
        description="Evaluates execution results for correctness and issues.",
        instruction=(
            "You are a research scientist responsible for evaluating the code execution "
            "output for a scientific experiment written by a programmer. If no code was "
            "executed, there was an error, or the code fails silently, return the success "
            'status as **false**. If the code includes a line "# [debug]" i.e "[debug]" '
            "as a comment, strictly treat this as a debugging experiment. In such cases, "
            "strictly return the success status as **false**, provide information that it "
            "was a debug code execution, give feedback and request the experiment to be "
            "retried with the new information. Otherwise, analyze the results and provide a "
            "short summary of the code output."
        ),
        output_key="analysis_feedback",
        output_schema=ExperimentAnalyst,
    )

    experiment_reviewer = LlmAgent(
        name="experiment_reviewer",
        model=resolved_model,
        description="Reviews the experiment design and analysis for quality.",
        instruction=(
            "You are a research scientist responsible for holistically reviewing the entire "
            "experiment pipeline, i.e., the generated code, the output, and the analysis "
            "w.r.t. the original experiment plan. Assess whether the experiment was "
            "faithfully implemented, i.e., whether the implementation follows the experiment "
            "plan without significant deviation and whether the hypothesis was in fact tested "
            "sufficiently. If you find issues or inconsistencies in any part of the "
            "experiment pipeline, return the success status as **false** and provide "
            "feedback about what is wrong. Otherwise, return the success status as **true** "
            "and provide a summary of the hypothesis, experiment results, and findings."
        ),
        output_key="review_feedback",
        output_schema=ExperimentReviewer,
    )

    experiment_reviser = LlmAgent(
        name="experiment_reviser",
        model=resolved_model,
        description="Produces revision guidance when the review fails.",
        instruction=(
            "You are a research scientist revisiting the most recent experiment, which could "
            "not be conducted correctly due to issues in the code or the formulation of the "
            "experiment plan,as indicated by the reviewer. Your goal is to revise this "
            "failed experiment plan by addressing the issues and limitations pointed out by "
            "the reviewer. The revised experiment plan should still aim to validate the most "
            "recent hypothesis. Do not provide the code yourself but explain in natural "
            "language what the experiment should do for a programmer. Strictly use only the "
            "dataset provided and do not create synthetic data or columns that cannot be "
            "derived from the given columns. The experiment should be creative, independent, "
            "and self-contained. Generally, in typical data-driven research, you will need "
            "to explore and visualize the data for possible high-level insights, clean, "
            "transform, or derive new variables from the dataset to be suited for the "
            "investigation, deep-dive into specific parts of the data for fine-grained "
            "analysis, perform data modeling, and run statistical tests."
        ),
        output_key="revised_experiment",
        output_schema=Experiment,
    )

    return {
        "experiment_generator": experiment_generator,
        "experiment_programmer": experiment_programmer,
        "experiment_analyst": experiment_analyst,
        "experiment_reviewer": experiment_reviewer,
        "experiment_reviser": experiment_reviser,
    }


class CodeExecutorAgent(BaseAgent):
    """Custom agent that executes experiment code without an LLM."""

    code_executor: SandboxExecutor

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        *,
        name: str,
        code_executor: SandboxExecutor,
    ) -> None:
        """Initialize the code executor agent.

        Args:
            name: The agent name.
            code_executor: Sandbox executor for running code.
        """
        data: dict[str, Any] = {
            "name": name,
            "description": "Executes experiment code and stores summarized outputs.",
            "code_executor": code_executor,
            "sub_agents": [],
        }
        super().__init__(**data)

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event]:
        """Execute the latest experiment code and emit a summary event."""
        code_str = str(ctx.session.state.get("experiment_code", ""))
        execution_result = await self.code_executor.run_code(code_str)
        summary = self._summarize_execution(execution_result)
        state_delta = {
            "execution_summary": summary,
            "execution_result_raw": execution_result,
        }
        content = types.Content(
            role="model",
            parts=[types.Part(text=summary)],
        )
        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            branch=ctx.branch,
            actions=EventActions(state_delta=state_delta),
            content=content,
        )

    def _summarize_execution(self, result: ExecutionResult) -> str:
        """Summarize execution output for downstream analysis."""
        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()
        pieces = [f"success: {result.success}"]
        if stdout:
            pieces.append(f"stdout:\n{stdout}")
        if stderr:
            pieces.append(f"stderr:\n{stderr}")
        if result.error:
            pieces.append(f"error: {result.error}")
        return "\n\n".join(pieces)


def create_code_executor_agent(
    *,
    backend: ExecutionBackend = "local",
    modal_app_name: str = _DEFAULT_MODAL_APP_NAME,
) -> CodeExecutorAgent:
    """Create a code executor agent configured for the chosen backend.

    Args:
        backend: The execution backend to use ("local" or "modal").
        modal_app_name: Modal app name when using the modal backend.

    Returns:
        A configured CodeExecutorAgent instance.
    """
    if backend == "modal":
        executor: SandboxExecutor = ModalEphemeralExecutor(app_name=modal_app_name)
    else:
        executor = InProcessExecutor()
    return CodeExecutorAgent(name="code_executor", code_executor=executor)


code_executor = create_code_executor_agent()


_DEFAULT_EXPERIMENT_AGENTS = create_experiment_agents()

experiment_generator = _DEFAULT_EXPERIMENT_AGENTS["experiment_generator"]
experiment_programmer = _DEFAULT_EXPERIMENT_AGENTS["experiment_programmer"]
experiment_analyst = _DEFAULT_EXPERIMENT_AGENTS["experiment_analyst"]
experiment_reviewer = _DEFAULT_EXPERIMENT_AGENTS["experiment_reviewer"]
experiment_reviser = _DEFAULT_EXPERIMENT_AGENTS["experiment_reviser"]


class ExperimentWorkflowAgent(BaseAgent):
    """Custom workflow agent orchestrating experiment iterations."""

    experiment_generator: LlmAgent
    experiment_programmer: LlmAgent
    experiment_analyst: LlmAgent
    experiment_reviewer: LlmAgent
    experiment_reviser: LlmAgent
    code_executor: BaseAgent
    max_programmer_attempts: int = 6

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
        code_executor: BaseAgent,
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
        data: dict[str, Any] = {
            "name": name,
            "description": (
                "Orchestrates programming, execution, analysis, review, revision, and"
                " generation for experiments."
            ),
            "experiment_generator": experiment_generator,
            "experiment_programmer": experiment_programmer,
            "experiment_analyst": experiment_analyst,
            "experiment_reviewer": experiment_reviewer,
            "experiment_reviser": experiment_reviser,
            "code_executor": code_executor,
            "max_programmer_attempts": max_programmer_attempts,
            "sub_agents": [
                experiment_programmer,
                code_executor,
                experiment_analyst,
                experiment_reviewer,
                experiment_reviser,
                experiment_generator,
            ],
        }
        super().__init__(**data)

    @override
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event]:
        """Run the experiment workflow with retries and review handling."""
        analysis_passed = False

        for attempt in range(1, self.max_programmer_attempts + 1):
            async for event in self.experiment_programmer.run_async(ctx):
                yield event

            code_payload = ctx.session.state.get("experiment_code_payload")
            code_value = self._extract_code(code_payload)
            if code_value:
                ctx.session.state["experiment_code"] = code_value

            async for event in self.code_executor.run_async(ctx):
                yield event

            async for event in self.experiment_analyst.run_async(ctx):
                yield event

            analysis_feedback = ctx.session.state.get("analysis_feedback")
            analysis_passed = self._parse_success(analysis_feedback, ExperimentAnalyst)
            ctx.session.state["analysis_passed"] = analysis_passed

            if analysis_passed:
                break

            if attempt == self.max_programmer_attempts:
                break

        async for event in self.experiment_reviewer.run_async(ctx):
            yield event

        review_feedback = ctx.session.state.get("review_feedback")
        review_passed = self._parse_success(review_feedback, ExperimentReviewer)
        ctx.session.state["review_passed"] = review_passed

        if not review_passed:
            async for event in self.experiment_reviser.run_async(ctx):
                yield event

            async for event in self.experiment_programmer.run_async(ctx):
                yield event

        async for event in self.experiment_generator.run_async(ctx):
            yield event

    def _parse_success(self, payload: object, schema: type[BaseModel]) -> bool:
        """Extract a success boolean from a structured payload."""

        # Interpret structured outputs stored in session state.
        class _SupportsSuccess(Protocol):
            success: bool

        if payload is None:
            return False
        if isinstance(payload, schema):
            return bool(cast(_SupportsSuccess, payload).success)
        if isinstance(payload, dict):
            parsed = schema.model_validate(payload)
            return bool(cast(_SupportsSuccess, parsed).success)
        if isinstance(payload, str):
            try:
                parsed = schema.model_validate_json(payload)
                return bool(cast(_SupportsSuccess, parsed).success)
            except ValueError:
                try:
                    parsed = schema.model_validate(json.loads(payload))
                    return bool(cast(_SupportsSuccess, parsed).success)
                except (ValueError, json.JSONDecodeError, TypeError):
                    return False
        return False

    def _extract_code(self, payload: object) -> str | None:
        """Extract code from a structured ExperimentCode payload."""
        # Normalize ExperimentCode payloads into raw code text for execution.
        if payload is None:
            return None
        if isinstance(payload, ExperimentCode):
            return payload.code
        if isinstance(payload, dict):
            return ExperimentCode.model_validate(payload).code
        if isinstance(payload, str):
            try:
                return ExperimentCode.model_validate_json(payload).code
            except ValueError:
                try:
                    return ExperimentCode.model_validate(json.loads(payload)).code
                except (ValueError, json.JSONDecodeError, TypeError):
                    return None
        return None


def create_experiment_workflow_agent(
    *,
    backend: ExecutionBackend = "local",
    modal_app_name: str = _DEFAULT_MODAL_APP_NAME,
    max_programmer_attempts: int = 6,
    model: LiteLlm | None = None,
) -> ExperimentWorkflowAgent:
    """Create an experiment workflow agent with a configurable executor backend.

    Args:
        backend: The execution backend to use ("local" or "modal").
        modal_app_name: Modal app name when using the modal backend.
        max_programmer_attempts: Maximum programmer retries after analysis failure.
        model: LiteLLM model instance for the experiment agents.

    Returns:
        A configured ExperimentWorkflowAgent instance.
    """
    agents = create_experiment_agents(model=model)
    return ExperimentWorkflowAgent(
        name="experiment_workflow_agent",
        experiment_generator=agents["experiment_generator"],
        experiment_programmer=agents["experiment_programmer"],
        experiment_analyst=agents["experiment_analyst"],
        experiment_reviewer=agents["experiment_reviewer"],
        experiment_reviser=agents["experiment_reviser"],
        code_executor=create_code_executor_agent(backend=backend, modal_app_name=modal_app_name),
        max_programmer_attempts=max_programmer_attempts,
    )


experiment_workflow_agent = ExperimentWorkflowAgent(
    name="experiment_workflow_agent",
    experiment_generator=experiment_generator,
    experiment_programmer=experiment_programmer,
    experiment_analyst=experiment_analyst,
    experiment_reviewer=experiment_reviewer,
    experiment_reviser=experiment_reviser,
    code_executor=code_executor,
)
