import asyncio
import concurrent.futures
import copy
import json
import os
from typing import Any

import autogen.agentchat.contrib.capabilities.transforms as transforms
from autogen import ConversableAgent, UserProxyAgent
from autogen.agentchat.contrib.capabilities import transform_messages
from autogen.coding import CodeBlock, CodeExecutor, CodeResult, LocalCommandLineCodeExecutor

from autodiscovery import llm
from autodiscovery.llm_usage import UsageTracker, record_ag2_response_usage
from autodiscovery.structured_outputs import (
    Experiment,
    ExperimentAnalyst,
    ExperimentCode,
    ExperimentHypothesisList,
    ExperimentList,
    ExperimentReviewer,
)

IMAGE_ANALYST_PROMPT = """Please analyze the given plot image and provide the following:

1. Plot Type: Identify the type of plot (e.g., heatmap, bar plot, scatter plot) and its purpose.
2. Axes:
    * Titles and labels, including units.
    * Value ranges for both axes.
3. Data Trends:
    * For scatter plots: note trends, clusters, or outliers.
    * For bar plots: highlight the tallest and shortest bars and patterns.
    * For heatmaps: identify areas of high and low values.
    etc...
4. Annotations and Legends: Describe key annotations or legends.
5. Statistical Insights: Provide insights based on the information presented in the plot."""


def _run_async(coro):
    """Run a coroutine from a synchronous context.

    Safe to call whether or not there is already a running event loop.
    """
    try:
        asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    except RuntimeError:
        return asyncio.run(coro)


class _ProcessBackendAdapter:
    """Wraps ProcessIPythonBackend in an async interface compatible with ModalSandboxExecutor."""

    def __init__(self, backend) -> None:
        self._backend = backend

    async def run_code(self, code: str, timeout_seconds: float | None = None):
        from asta_sandbox import ExecutionError, ExecutionResult, RichOutput

        result = self._backend.run_cell(code, timeout_s=timeout_seconds)
        error = None
        if result.get("error"):
            err = result["error"]
            tb = err.get("traceback", "")
            error = ExecutionError(
                etype=err.get("type"),
                evalue=err.get("message"),
                traceback=(tb,) if tb else (),
            )
        rich_outputs = tuple(
            RichOutput(output_type="display_data", data=ro, metadata={})
            for ro in result.get("rich_outputs", [])
            if ro
        )
        return ExecutionResult(
            stdout=result.get("stdout", ""),
            stderr=result.get("stderr", ""),
            success=result.get("success", False),
            rich_outputs=rich_outputs,
            error=error,
        )


class ModalSandboxExecutor(CodeExecutor):
    """Wraps an async sandbox executor to satisfy Autogen's synchronous CodeExecutor interface."""

    def __init__(
        self,
        backend,
        *,
        vision_model: str,
        timeout: int = 30 * 60,
        usage_tracker: UsageTracker | None = None,
    ):
        """Initialize the sandbox executor wrapper.

        Args:
            backend: Async sandbox executor (ModalEphemeralExecutor or _ProcessBackendAdapter)
            timeout: Timeout in seconds (for Autogen compatibility)
            vision_model: Vision model, as litellm's ``<provider>/<model>``
            usage_tracker: Optional usage tracker for image analysis calls.
        """
        self._executor = backend
        self._timeout = timeout
        self.vision_model = vision_model
        self._usage_tracker = usage_tracker
        self._usage_node_id: str | None = None

    def _analyze_image(self, image_data: str) -> str:
        """Analyze a base64-encoded image using the configured vision model.

        Args:
            image_data: Base64-encoded image data

        Returns:
            Analysis text
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a research scientist responsible for analyzing plots and figures "
                    "from running experiments and providing detailed descriptions."
                ),
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": IMAGE_ANALYST_PROMPT},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_data}"},
                    },
                ],
            },
        ]
        # Deliberately not caught here: execute_code_blocks already wraps this
        # call and records "Failed to analyze image: ..." per figure, which is
        # what main did. Swallowing it here would duplicate that handling and
        # hide the failure behind a different message.
        response = llm.complete(self.vision_model, messages)

        if self._usage_tracker is not None:
            self._usage_tracker.record_response(
                response,
                source=llm.provider_of(self.vision_model),
                request_model=self.vision_model,
                component="image_analysis.modal",
                agent_name="code_executor",
                node_id=self._usage_node_id,
            )
        return response.choices[0].message.content

    def execute_code_blocks(self, code_blocks: list[CodeBlock]) -> CodeResult:
        """Execute code blocks using the sandbox backend.

        Args:
            code_blocks: List of code blocks to execute

        Returns:
            CodeResult with execution output and success status
        """
        code = "\n".join(block.code for block in code_blocks)

        print("\n[CodeExecutor] Executing code in sandbox...")
        print(f"[CodeExecutor] Code length: {len(code)} characters")

        try:
            result = _run_async(self._executor.run_code(code, timeout_seconds=self._timeout))

            print("[CodeExecutor] Execution completed")
            print(f"[CodeExecutor] Success: {result.success}")

            output = result.stdout or ""

            print(f"[CodeExecutor] Stdout length: {len(output)} characters")

            if result.stderr:
                print(f"[CodeExecutor] Stderr: {result.stderr[:200]}")
                output += f"\nSTDERR:\n{result.stderr}"

            if not result.success:
                if result.error:
                    tb = "".join(result.error.traceback)
                    error_msg = f"{result.error.etype}: {result.error.evalue}"
                    if tb:
                        error_msg += f"\n{tb}"
                elif not result.stdout and not result.stderr:
                    # Imprecise: asta-sandbox doesn't yet surface a typed TimeoutError,
                    # so empty output on failure is our best signal. Fix this when
                    # asta-sandbox propagates timeout as a proper ExecutionError.
                    error_msg = f"Execution timed out after {self._timeout}s"
                else:
                    error_msg = "Unknown error"
                print(f"[CodeExecutor] Error: {error_msg}")
                output += f"\nERROR: {error_msg}"

            if not output.strip():
                output = "[CodeExecutor] Code executed but produced no output"
                print("[CodeExecutor] Warning: No output produced")

            # Store rich output data dicts for image analysis
            self._last_rich_outputs = [ro.data for ro in result.rich_outputs]

            if self._last_rich_outputs:
                print(f"[CodeExecutor] Found {len(self._last_rich_outputs)} rich outputs")

            if self._last_rich_outputs:
                image_analyses = []
                for idx, rich_output in enumerate(self._last_rich_outputs):
                    if "image/png" in rich_output:
                        png_data = rich_output["image/png"]
                        try:
                            analysis = self._analyze_image(png_data)
                            image_analyses.append(
                                f"\n=== Plot Analysis (figure {idx + 1}) ===\n{analysis}\n{'=' * 50}"
                            )
                        except Exception as e:
                            image_analyses.append(
                                f"\n=== Plot Analysis (figure {idx + 1}) ===\nFailed to analyze image: {str(e)}\n{'=' * 50}"
                            )

                if image_analyses:
                    output += "\n" + "\n".join(image_analyses)

            return CodeResult(exit_code=0 if result.success else 1, output=output)

        except Exception as e:
            import traceback

            error_details = traceback.format_exc()
            print(f"[CodeExecutor] Exception occurred: {str(e)}")
            print(f"[CodeExecutor] Traceback:\n{error_details}")
            return CodeResult(
                exit_code=1, output=f"Execution failed: {str(e)}\n\nTraceback:\n{error_details}"
            )

    def get_last_rich_outputs(self):
        """Get rich outputs from the last execution."""
        return getattr(self, "_last_rich_outputs", [])

    def set_usage_context(
        self,
        usage_tracker: UsageTracker | None,
        node_id: str | None = None,
    ) -> None:
        """Set usage tracking context for subsequent image analysis requests.

        Args:
            usage_tracker: Usage tracker instance.
            node_id: Node id to attach to usage events.
        """
        self._usage_tracker = usage_tracker
        self._usage_node_id = node_id

    @property
    def timeout(self) -> int:
        """Return the timeout value."""
        return self._timeout

    def restart(self) -> None:
        """Restart the executor (creates a new IPython kernel session)."""
        # For Modal sandbox, we don't need to explicitly restart
        # Each execution is isolated
        pass

    @property
    def code_extractor(self):
        """Return the code extractor for this executor."""
        # Use default markdown code extractor
        from autogen.coding import MarkdownCodeExtractor

        return MarkdownCodeExtractor()


def parse_bucket_path(bucket_path: str) -> tuple[str, str]:
    """Parse GCS bucket path into bucket name and key prefix.

    Args:
        bucket_path: Path like "gs://bucket-name/path/to/prefix/"

    Returns:
        Tuple of (bucket_name, key_prefix)
    """
    # Remove gs:// prefix if present
    path = bucket_path.replace("gs://", "")

    # Split into bucket and prefix
    parts = path.split("/", 1)
    bucket_name = parts[0]
    key_prefix = parts[1] if len(parts) > 1 else ""

    # Ensure key_prefix ends with / if it's not empty
    if key_prefix and not key_prefix.endswith("/"):
        key_prefix += "/"

    return bucket_name, key_prefix


def build_image_analysis_patch(vision_model: str) -> str:
    """Build the matplotlib patch injected into locally executed experiment code.

    Only the ``local`` backend uses this, and it runs in-process, so the patch
    can call straight back into :mod:`autodiscovery.llm` rather than
    reimplementing provider routing and auth for the execution context.
    """
    # Fail fast here, in the parent, rather than inside generated code.
    llm.provider_of(vision_model)
    template = """\
import matplotlib.pyplot as plt
import functools
import base64
import json
from io import BytesIO

from autodiscovery import llm
from autodiscovery.llm_usage import LOCAL_IMAGE_USAGE_MARKER

VISION_MODEL = __VISION_MODEL__
image_analyst_prompt = __IMAGE_ANALYST_PROMPT__


def image_to_text():
    for fig_num in plt.get_fignums():
        fig = plt.figure(fig_num)
        with BytesIO() as buf:
            fig.savefig(buf, format='png', dpi=200)
            buf.seek(0)
            base64_image = base64.b64encode(buf.read()).decode('utf-8')
            messages = [
                {
                    'role': 'system',
                    'content': 'You are a research scientist responsible for analyzing plots and figures from running experiments and providing detailed descriptions.'
                },
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': image_analyst_prompt},
                        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + base64_image}},
                    ]
                }
            ]
            try:
                response = llm.complete(VISION_MODEL, messages, max_tokens=1000)
            except Exception as exc:
                print('Image analysis skipped: ' + str(exc))
                plt.close(fig)
                continue
            usage = getattr(response, 'usage', None)
            if usage is not None:
                print(LOCAL_IMAGE_USAGE_MARKER + json.dumps({
                    'source': llm.provider_of(VISION_MODEL),
                    'component': 'image_analysis.local',
                    'agent_name': 'code_executor',
                    'model': getattr(response, 'model', VISION_MODEL),
                    'prompt_tokens': getattr(usage, 'prompt_tokens', 0) or 0,
                    'completion_tokens': getattr(usage, 'completion_tokens', 0) or 0,
                    'total_tokens': getattr(usage, 'total_tokens', 0) or 0,
                    # The response is only reachable in here, so the cost is
                    # priced sandbox-side and carried out through the marker.
                    'cost': llm.cost_of(response, VISION_MODEL),
                }, sort_keys=True))
            print("\\n=== Plot Analysis (fig. {{}}) ===\\n".format(fig_num))
            print(response.choices[0].message.content)
            print("\\n" + "="*50)

        plt.close(fig)


def patch_matplotlib_show():
    plt.show = functools.partial(image_to_text)


patch_matplotlib_show()
"""
    return template.replace("__VISION_MODEL__", repr(vision_model)).replace(
        "__IMAGE_ANALYST_PROMPT__", repr(IMAGE_ANALYST_PROMPT)
    )


class CodeBlockWrapperTransform(transforms.MessageTransform):
    def __init__(self, vision_model: str):
        self.image_analysis_patch = build_image_analysis_patch(vision_model)

    def apply_transform(self, messages: list[dict]) -> list[dict]:
        # Deep copy messages to avoid modifying the original
        transformed_messages = copy.deepcopy(messages)
        message = transformed_messages[-1]

        try:
            code = json.loads(message["content"]).get("code", "# Failed to parse code from message")
        except json.JSONDecodeError:
            code = "# Failed to parse code from message"

        message["content"] = f"```python\n{self.image_analysis_patch}\n\n{code}\n```"

        return transformed_messages

    def get_logs(
        self, pre_transform_messages: list[dict], post_transform_messages: list[dict]
    ) -> tuple[str, bool]:
        return "CodeBlockWrapperTransform", True


def code_transform_working_dir(backend: str, work_dir: str, modal_working_dir: str | None) -> str:
    """Return the directory the code transform should ``os.chdir`` into per cell.

    For the process/local backends this must be **absolute**: their subprocess
    already starts with ``cwd=work_dir``, so a relative path injected by
    :class:`SimpleCodeBlockTransform` would stack (``work_dir/work_dir``) and
    raise ``FileNotFoundError``. modal uses its absolute mount path (``/data``),
    which is idempotent regardless of the sandbox's starting directory.
    """
    if backend == "modal":
        return modal_working_dir
    return os.path.abspath(work_dir)


class SimpleCodeBlockTransform(transforms.MessageTransform):
    """Simple transform that extracts code from JSON and wraps it in markdown code blocks."""

    def __init__(self, working_dir="/data"):
        """Initialize with optional working directory to change to before executing code."""
        self.working_dir = working_dir

    def apply_transform(self, messages: list[dict]) -> list[dict]:
        # Deep copy messages to avoid modifying the original
        transformed_messages = copy.deepcopy(messages)
        message = transformed_messages[-1]

        try:
            code = json.loads(message["content"]).get("code", "# Failed to parse code from message")
        except json.JSONDecodeError:
            code = "# Failed to parse code from message"

        # Prepend code to change to the working directory where data is mounted
        # This allows code to find files by their basename
        if self.working_dir:
            chdir_code = f"import os\nos.chdir('{self.working_dir}')\n\n"
            code = chdir_code + code

        # Wrap in markdown code blocks
        message["content"] = f"```python\n{code}\n```"

        return transformed_messages

    def get_logs(
        self, pre_transform_messages: list[dict], post_transform_messages: list[dict]
    ) -> tuple[str, bool]:
        return "SimpleCodeBlockTransform", True


class LiteLLMAG2Client:
    """AG2 ModelClient that routes every provider through litellm.

    AG2 0.10 ships clients for a fixed set of providers and picks one by
    ``api_type``. Registering this instead means AG2 inherits litellm's provider
    list, so a new provider needs no code here -- only a ``<provider>/<model>``
    model flag.
    """

    def __init__(self, config: dict[str, Any], **_: Any) -> None:
        """Initialize the adapter from an AG2 model configuration."""
        self.model = str(config["model"])
        self.config = config

    def create(self, params: dict[str, Any]) -> Any:
        """Run one completion and return a litellm response.

        Args:
            params: AG2 request parameters.

        Returns:
            A litellm ``ModelResponse``, which is OpenAI-shaped and so satisfies
            AG2's expectations directly.
        """
        kwargs = {
            key: params[key]
            for key in ("temperature", "reasoning_effort", "response_format", "n", "stream")
            if params.get(key) is not None
        }
        if not llm.accepts_temperature(self.model):
            kwargs.pop("temperature", None)
        response = llm.complete(self.model, params["messages"], **kwargs)
        # This is the single point every AG2 response flows through, so usage is
        # recorded here rather than by patching AG2's OpenAIWrapper.
        record_ag2_response_usage(
            response,
            agent_name=self.config.get("agent_name"),
            request_model=self.model,
        )
        return response

    def message_retrieval(self, response: Any) -> list[str]:
        """Extract assistant message content from a response."""
        return [choice.message.content for choice in response.choices]

    def cost(self, response: Any) -> float:
        """Return the response cost litellm computed, or zero."""
        return llm.reported_cost(response) or 0.0

    @staticmethod
    def get_usage(response: Any) -> dict[str, Any]:
        """Return AG2-compatible token usage metadata.

        AG2's interface requires a number, so an unpriced model reports zero
        here. The usage tracker keeps the distinction between free and unpriced
        that this loses; see :func:`autodiscovery.llm.cost_of`.
        """
        usage = getattr(response, "usage", None)
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            "cost": llm.reported_cost(response) or 0.0,
            "model": getattr(response, "model", None),
        }


def get_llm_config(
    model_name: str,
    temperature: float | None = None,
    reasoning_effort: str | None = None,
    timeout: int = 600,
) -> dict[str, Any]:
    """Build an AG2 llm_config backed by :class:`LiteLLMAG2Client`.

    Args:
        model_name: Model name, as litellm's ``<provider>/<model>``.
        temperature: Sampling temperature. Omitted for models that reject it.
        reasoning_effort: Optional reasoning effort; litellm drops it where
            unsupported.
        timeout: Request timeout in seconds.

    Returns:
        Configuration dict for AG2.
    """
    llm.provider_of(model_name)  # fail fast on an unusable name
    entry: dict[str, Any] = {
        "model": model_name,
        "model_client_cls": LiteLLMAG2Client.__name__,
        "timeout": timeout,
    }
    if temperature is not None and llm.accepts_temperature(model_name):
        entry["temperature"] = temperature
    if reasoning_effort is not None:
        entry["reasoning_effort"] = reasoning_effort
    return {"config_list": [entry], "cache_seed": None}


def get_agents(
    work_dir,
    *,
    model_name,
    vision_model,
    temperature=None,
    reasoning_effort=None,
    branching_factor=3,
    user_query=None,
    experiment_first=False,
    code_timeout=30 * 60,
    backend="process",
    bucket_path=None,
    dataset_paths=None,
    usage_tracker: UsageTracker | None = None,
) -> dict[str, ConversableAgent]:
    """Build and return the conversational agents used by AutoDiscovery.

    Args:
        work_dir: Working directory for code execution.
        model_name: Model for AG2 conversational agents, as litellm's
            ``<provider>/<model>``.
        temperature: Sampling temperature for non-reasoning models.
        reasoning_effort: Reasoning effort for compatible models.
        branching_factor: Number of experiment candidates to request.
        user_query: Optional user query injected into generator prompts.
        experiment_first: Whether generator returns experiment-first outputs.
        code_timeout: Timeout in seconds for code execution.
        backend: Code execution backend (local, process, or modal).
        bucket_path: Optional GCS bucket path for Modal datasets.
        dataset_paths: Optional dataset paths (reserved for future use).
        vision_model: Vision model for plot analysis, as litellm's
            ``<provider>/<model>``.
        usage_tracker: Optional usage tracker for direct image-analysis calls.

    Returns:
        Dictionary mapping agent name to agent instance.
    """
    llm_config = get_llm_config(
        model_name=model_name,
        temperature=temperature,
        reasoning_effort=reasoning_effort,
    )

    # Create token limit transform.
    # `model` must be set explicitly: MessageTokenLimiter defaults to "gpt-3.5-turbo-0613"
    # and silently caps max_tokens_per_message to that model's 4096-token limit.
    # The value only drives tokenizer choice and the cap lookup, so any large-context OpenAI model works.
    token_limit_capability = transform_messages.TransformMessages(
        transforms=[
            transforms.MessageTokenLimiter(
                max_tokens_per_message=10_000, min_tokens=12_000, model="gpt-4o"
            )
        ]
    )

    # Experiment Generator
    _user_query_or_empty = f"{user_query}\n\n" if user_query is not None else ""

    experiment_generator = ConversableAgent(
        name="experiment_generator",
        llm_config={
            **llm_config,
            "response_format": ExperimentList if not experiment_first else ExperimentHypothesisList,
        },
        system_message=(
            "You are a research scientist who is interested in doing open-ended, data-driven research using the provided dataset(s). "
            f"{_user_query_or_empty}"
            f"Be creative and think of new and interesting verifiable {'experiments' if experiment_first else 'hypotheses'} and corresponding {'hypotheses' if experiment_first else 'experiments'}. "
            "The hypothesis should be a falsifiable statement that can be sufficiently tested by an experiment using the provided data. "
            "Explain in natural language what this experiment plan is so that a programmer can implement it (do not provide the code yourself). "
            "Remember, you are interested in open-ended research, so your proposals may be exploratory in nature and may have only an indirect connection to the previous explorations provided. "
            "Here are some instructions that you must follow:\n"
            "1. Strictly use only the dataset(s) provided and do not simulate dummy/synthetic data or columns that cannot be derived from the existing columns.\n"
            "2. Each hypothesis (and experiment plan) should be creative, independent, and self-contained.\n"
            "3. Use the prior experiments/hypotheses as inspiration to think of interesting and creative new experiments/hypotheses. However, do not repeat the same experiments/hypotheses.\n\n"
            "Here is a possible approach to coming up with a new hypothesis and experiment plan:\n"
            "1. Find an interesting context: this could be a specific subset of the data. E.g., if the dataset has multiple categorical variables, you could split the data based on specific values of such variables, which would then allow you to validate a hypothesis in the specific contexts defined by the values of those variables.\n"
            "2. Find interesting variables: these could be the columns in the dataset that you find interesting or relevant to the context. You are allowed and encouraged to create composite variables derived from the existing variables.\n"
            "3. Find interesting relationships: these are interactions between the variables that you find interesting or relevant to the context. You are encouraged to propose experiments involving complex predictive or causal models.\n"
            "4. You must require that your proposed hypotheses are verifiable using robust statistical tests. Remember, your programmer can install python packages via pip which can allow it to write code for complex statistical analyses.\n"
            "5. Multiple datasets: If you are provided with more than one dataset, then try to also propose hypotheses that utilize contexts, variables, and relationships across datasets, e.g., this may involve using join or similar operations.\n\n"
            "Generally, in typical data-driven research, you will need to explore and visualize the data for possible high-level insights, clean, transform, or derive new variables from the dataset to be suited for the investigation, deep-dive into specific parts of the data for fine-grained analysis, perform data modeling, and run statistical tests. "
            f"Now, generate exactly {branching_factor} new hypotheses with their experiment plans."
        ),
        human_input_mode="NEVER",
    )

    if backend == "process":
        # The process backend places an `install-package` script on PATH
        # that installs into a per-cell temp directory via uv.
        install_snippet = """\nimport subprocess

def install(package):
    subprocess.check_call(["install-package", package])\n\n\n"""
    else:
        install_snippet = """\nimport subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", package])\n\n\n"""

    # Experiment Programmer
    experiment_programmer = ConversableAgent(
        name="experiment_programmer",
        llm_config={**llm_config, "response_format": ExperimentCode},
        system_message=(
            "You are a scientific experiment programmer proficient in writing python code given an experiment plan. "
            "Your code will be included in a python file that is executed and any relevant results should be printed to standard out or presented using plt.show appropriately. "
            "Make sure you provide python code in the proper format to execute. "
            "Ensure your code is clean and concise, and include debug statements only when they are absolutely necessary. "
            "Use only the dataset given and do not assume any other files are available. The state is not preserved between code blocks, so do not assume any variables or imports from previous code blocks. "
            "Import any libraries you need to use. Always attempt to import a library before installing it (it may already be installed). "
            "If you need to install a library, use the following code example:"
            f"{install_snippet}"
            "When installing python packages, use the --quiet option to minimize unnecessary output."
            "Prefer using installed libraries over installing new libraries whenever possible. "
            "If possible, instead of downgrading library versions, try to adapt your code to work with a more updated version that is already installed. "
            "Never attempt to create a new environment. Always use the current environment. "
            "If the code requires generating plots, use plt.show (not plt.savefig).  "
            "Avoid printing the whole data structure to the console directly if it is large; instead, print concise results that are directly relevant to the experiment. "
            "You are allowed 6 total attempts to run the code, including debugging attempts.\n\n"
            "Debugging instructions:\n"
            "1. Only debug if you are either unsure about the executability or validity of the code (i.e., whether it satisfies the proposed experiment).\n"
            '2. If the code you are writing is intended for debugging, the first line of your code must be "# [debug]" only.\n'
            '3. DO NOT use "[debug]" anywhere else in your code.\n'
            "4. DO NOT combine any debug code and the actual experiment implementation code; keep them separate.\n"
            "5. For each experiment, you are allowed to debug at most 3 times.\n"
            "6. As much as possible, minimize the number of debugging steps you use."
        ),
        human_input_mode="NEVER",
    )

    # Experiment Analyst
    experiment_analyst = ConversableAgent(
        name="experiment_code_analyst",
        llm_config={**llm_config, "response_format": ExperimentAnalyst},
        system_message=(
            "You are a research scientist responsible for evaluating the code execution output for a scientific experiment written by a programmer. "
            "If no code was executed, there was an error, or the code fails silently, return the success status as **false**. "
            'If the code includes a line "# [debug]" i.e "[debug]" as a comment, strictly treat this as a debugging experiment. '
            "In such cases, strictly return the success status as **false**, provide information that it was a debug code execution, "
            "give feedback and request the experiment to be retried with the new information. "
            "Otherwise, analyze the results and provide a short summary of the code output."
        ),
        human_input_mode="NEVER",
    )

    # Experiment Reviewer
    experiment_reviewer = ConversableAgent(
        name="experiment_reviewer",
        llm_config={**llm_config, "response_format": ExperimentReviewer},
        system_message=(
            "You are a research scientist responsible for holistically reviewing the entire experiment pipeline, i.e., the generated code, the output, and the analysis w.r.t. the original experiment plan. "
            "Assess whether the experiment was faithfully implemented, i.e., whether the implementation follows the experiment plan without significant deviation and whether the hypothesis was in fact tested sufficiently. "
            "If you find issues or inconsistencies in any part of the experiment pipeline, return the success status as **false** and provide feedback about what is wrong. "
            "Otherwise, return the success status as **true** and provide a summary of the hypothesis, experiment results, and findings."
        ),
        human_input_mode="NEVER",
    )

    # Experiment Reviser
    experiment_reviser = ConversableAgent(
        name="experiment_reviser",
        llm_config={**llm_config, "response_format": Experiment},
        system_message=(
            "You are a research scientist revisiting the most recent experiment, which could not be conducted correctly due to issues in the code or the formulation of the experiment plan,"
            "as indicated by the reviewer. Your goal is to revise this failed experiment plan by addressing the issues and limitations pointed out by the reviewer. "
            "The revised experiment plan should still aim to validate the most recent hypothesis. "
            "Do not provide the code yourself but explain in natural language what the experiment should do for a programmer. "
            "Strictly use only the dataset provided and do not create synthetic data or columns that cannot be derived from the given columns. "
            "The experiment should be creative, independent, and self-contained. "
            "Generally, in typical data-driven research, you will need to explore and visualize the data for possible high-level insights, clean, transform, or derive new variables from the dataset to be suited for the investigation, deep-dive into specific parts of the data for fine-grained analysis, perform data modeling, and run statistical tests."
        ),
        human_input_mode="NEVER",
    )

    ## Code Executor Setup
    modal_working_dir = None  # Track working directory for Modal sandbox

    if backend == "modal":
        # Use Modal sandbox for code execution
        if not bucket_path:
            raise ValueError("bucket_path is required when backend is 'modal'")

        import modal
        from asta_sandbox import CloudShare
        from asta_sandbox.backends.modal_ephemeral import ModalEphemeralExecutor
        from autodiscovery_modal.ipython_session import build_sandbox_image

        # Parse bucket path
        bucket_name, key_prefix = parse_bucket_path(bucket_path)

        modal_mount_path = "/data"
        modal_working_dir = modal_mount_path

        # Get Modal configuration from environment
        app_name = os.environ.get("MODAL_APP_NAME", "asta-autodiscovery")
        secret_name = os.environ.get("MODAL_BUCKET_SECRET", "example-bucket-secret")
        bucket_endpoint_url = os.environ.get("GCS_ENDPOINT_URL", "https://storage.googleapis.com")

        sandbox_image = build_sandbox_image(
            extra_packages=[
                "numpy",
                "pandas",
                "matplotlib",
                "matplotlib-inline",
                "seaborn",
                "scikit-learn",
                "scipy",
                "statsmodels",
            ]
        )

        cloud_share = CloudShare(
            dest=modal_mount_path,
            bucket=bucket_name,
            key_prefix=key_prefix,
            read_only=True,
            bucket_endpoint_url=bucket_endpoint_url,
            modal_secret=modal.Secret.from_name(secret_name),
        )

        # sandbox_timeout_s covers startup + execution + teardown, so it must exceed
        # code_timeout (the process-level limit). The buffer gives time for Modal sandbox
        # startup and for the finally-block terminate() to run after the process times out.
        _SANDBOX_OVERHEAD_S = 60
        modal_executor = ModalEphemeralExecutor(
            app_name=app_name,
            image=sandbox_image,
            environment={"DATASET_ROOT": modal_mount_path},
            sandbox_timeout_s=code_timeout + _SANDBOX_OVERHEAD_S,
        )
        _run_async(modal_executor.add_shares(cloud_share))

        executor = ModalSandboxExecutor(
            modal_executor,
            timeout=code_timeout,
            vision_model=vision_model,
            usage_tracker=usage_tracker,
        )
        print(
            f"Using Modal sandbox with bucket gs://{bucket_name}/{key_prefix} mounted at {modal_mount_path}"
        )
        print(f"Working directory will be: {modal_working_dir}")
    elif backend == "process":
        # Use isolated subprocess for code execution
        from code_execution import ProcessIPythonBackend

        process_backend = ProcessIPythonBackend(cwd=work_dir)
        executor = ModalSandboxExecutor(
            _ProcessBackendAdapter(process_backend),
            timeout=code_timeout,
            vision_model=vision_model,
            usage_tracker=usage_tracker,
        )
        print(f"Using process backend with work_dir: {work_dir}")
    else:
        # Use local code executor (in-process, no isolation)
        executor = LocalCommandLineCodeExecutor(
            timeout=code_timeout,
            work_dir=work_dir,
        )

    # Create an agent with code executor configuration.
    code_executor = ConversableAgent(
        "code_executor",
        llm_config=False,
        code_execution_config={"executor": executor},
        human_input_mode="NEVER",
    )

    # Apply appropriate transform based on executor type
    if backend in ("modal", "process"):
        # For sandbox-style backends, use simple transform without image analysis patch
        # (the executor handles image analysis internally)
        # Pass the working_dir so code can change to that directory.
        sandbox_working_dir = code_transform_working_dir(backend, work_dir, modal_working_dir)
        transform_messages_capability = transform_messages.TransformMessages(
            transforms=[SimpleCodeBlockTransform(working_dir=sandbox_working_dir)]
        )
        transform_messages_capability.add_to_agent(code_executor)
    else:
        # For local executor, use full transform with image analysis patch
        transform_messages_capability = transform_messages.TransformMessages(
            transforms=[CodeBlockWrapperTransform(vision_model=vision_model)]
        )
        transform_messages_capability.add_to_agent(code_executor)

    user_proxy = UserProxyAgent(
        name="user_proxy",
        description="Responsible for providing the initial query",
        code_execution_config=False,
        human_input_mode="NEVER",
    )

    agents = [
        experiment_generator,
        experiment_programmer,
        experiment_analyst,
        experiment_reviewer,
        experiment_reviser,
        code_executor,
        user_proxy,
    ]

    for agent in agents:
        if agent.llm_config is not False:
            agent.register_model_client(LiteLLMAG2Client)

    # Apply token limit to all agents
    for agent in agents:
        token_limit_capability.add_to_agent(agent)

    agents_dict = {agent.name: agent for agent in agents}
    return agents_dict
