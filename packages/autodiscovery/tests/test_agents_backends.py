"""Tests for how ``get_agents`` wires each code-execution backend.

Guards the invariant that plot interpretation happens *outside* the code
execution environment: every backend hands figures back as rich outputs and the
parent process is the only place a vision model is called. Nothing is injected
into the agent's code, so the executed program is the program the agent wrote.
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import autodiscovery.agents as agents_module
from autodiscovery.agents import (
    SandboxCodeExecutor,
    SimpleCodeBlockTransform,
    _IPythonBackendAdapter,
    get_agents,
)

_MODEL = "openai/gpt-4o"


def _code_executor(backend: str, work_dir: str):
    agents = get_agents(
        work_dir,
        model_name=_MODEL,
        vision_model=_MODEL,
        backend=backend,
    )
    return agents["code_executor"].code_executor


def test_local_backend_returns_rich_outputs(tmp_path) -> None:
    """`local` used to have no rich outputs at all, so figures were never persisted."""
    executor = _code_executor("local", str(tmp_path))

    assert isinstance(executor, SandboxCodeExecutor)
    # run._get_executor_rich_outputs keys off this method; without it the node's
    # rich_outputs/ entry is empty and the report shows no figures.
    assert executor.get_last_rich_outputs() == []


def test_no_image_analysis_is_injected_into_executed_code(tmp_path) -> None:
    """The transform prefixes a chdir and nothing else -- no vision model, no markers."""
    transform = SimpleCodeBlockTransform(working_dir=str(tmp_path))
    content = transform.apply_transform([{"content": json.dumps({"code": "plt.show()"})}])[-1][
        "content"
    ]

    assert "plt.show" in content
    assert "llm.complete" not in content
    assert "image_analyst_prompt" not in content
    assert "__AUTODISCOVERY_LLM_USAGE__" not in content


def test_code_injection_helpers_are_gone() -> None:
    """The injected patch and its stdout-marker transport no longer exist."""
    assert not hasattr(agents_module, "build_image_analysis_patch")
    assert not hasattr(agents_module, "CodeBlockWrapperTransform")

    import autodiscovery.llm_usage as llm_usage

    assert not hasattr(llm_usage, "LOCAL_IMAGE_USAGE_MARKER")
    assert not hasattr(llm_usage, "extract_local_image_usage_markers")


def test_adapter_surfaces_rich_outputs_and_honors_use_subprocess() -> None:
    """The adapter is what makes a synchronous IPython backend look like a sandbox."""
    calls: list[dict] = []

    class _Backend:
        def run_cell(self, code, *, use_subprocess=False, timeout_s=None):
            calls.append({"use_subprocess": use_subprocess, "timeout_s": timeout_s})
            return {
                "stdout": "ok",
                "stderr": "",
                "success": True,
                "rich_outputs": [{"image/png": "Zm9v"}],
            }

    adapter = _IPythonBackendAdapter(_Backend(), use_subprocess=True)
    result = asyncio.run(adapter.run_code("print('ok')", timeout_seconds=5))

    assert calls == [{"use_subprocess": True, "timeout_s": 5}]
    assert result.success
    assert [ro.data for ro in result.rich_outputs] == [{"image/png": "Zm9v"}]


def test_figures_are_analyzed_once_in_the_parent_process(monkeypatch, tmp_path) -> None:
    """Every PNG the backend returns is analyzed here, and the usage is tracked."""
    recorded: list[dict] = []

    class _Tracker:
        def record_response(self, response, **kwargs):
            recorded.append(kwargs)

    class _Backend:
        async def run_code(self, code, timeout_seconds=None):
            return SimpleNamespace(
                stdout="printed",
                stderr="",
                success=True,
                error=None,
                rich_outputs=(
                    SimpleNamespace(data={"image/png": "one"}),
                    SimpleNamespace(data={"image/png": "two"}),
                    SimpleNamespace(data={"text/plain": "not a figure"}),
                ),
            )

    monkeypatch.setattr(
        agents_module.llm,
        "complete",
        lambda model, messages, **kwargs: SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="an analysis"))]
        ),
    )

    executor = SandboxCodeExecutor(_Backend(), vision_model=_MODEL, usage_tracker=_Tracker())
    result = executor.execute_code_blocks(
        [SimpleNamespace(code="print('printed')", language="python")]
    )

    assert result.exit_code == 0
    assert result.output.count("an analysis") == 2
    assert [call["component"] for call in recorded] == ["image_analysis", "image_analysis"]
