"""Tests for the cap on code-executor output size.

Generated code regularly prints an entire dataset; the executor's output becomes a
chat message that is re-serialized into every later LLM request, so an uncapped
output OOM-kills the job (observed: 676 MB of stdout, container SIGKILLed).
"""

import autodiscovery.agents as agents
import pytest
from autodiscovery.agents import (
    MAX_CODE_OUTPUT_CHARS,
    ModalSandboxExecutor,
    _truncate_output,
)


def test_short_output_is_returned_verbatim():
    assert _truncate_output("hello") == "hello"


def test_output_at_the_limit_is_not_truncated():
    output = "x" * MAX_CODE_OUTPUT_CHARS
    assert _truncate_output(output) == output


def test_tiny_fixed_cap_cannot_leak_the_full_output(monkeypatch):
    monkeypatch.setattr(agents, "MAX_CODE_OUTPUT_CHARS", 32)

    truncated = _truncate_output("x" * 1_000)

    assert len(truncated) == 32
    assert "output truncated" in truncated


def test_one_character_over_limit_reports_exact_omission():
    output = "x" * (MAX_CODE_OUTPUT_CHARS + 1)

    truncated = _truncate_output(output)

    retained = truncated.count("x")
    assert len(truncated) == MAX_CODE_OUTPUT_CHARS
    assert f"output truncated: {len(output) - retained} of {len(output)}" in truncated


def test_long_output_keeps_both_ends_and_reports_the_drop():
    output = "H" * 10_000 + "M" * 80_000 + "T" * 10_000
    truncated = _truncate_output(output)

    assert truncated.startswith("H")
    assert truncated.endswith("T")
    assert "output truncated" in truncated
    assert "of 100000 characters omitted" in truncated
    assert "M" not in truncated
    assert len(truncated) == MAX_CODE_OUTPUT_CHARS


class _StubBackend:
    """Sandbox backend returning a canned result, mirroring asta_sandbox's shape."""

    def __init__(self, stdout, stderr=""):
        self._stdout = stdout
        self._stderr = stderr

    async def run_code(self, code, timeout_seconds=None):
        from asta_sandbox import ExecutionResult

        return ExecutionResult(
            stdout=self._stdout,
            stderr=self._stderr,
            success=True,
            rich_outputs=(),
            error=None,
        )


def _executor(stdout, stderr="", **kwargs):
    return ModalSandboxExecutor(
        _StubBackend(stdout, stderr), vision_model="vertex_ai/gemini-3.7-flash", **kwargs
    )


def test_execute_code_blocks_caps_a_giant_stdout():
    from autogen.coding import CodeBlock

    executor = _executor("x" * 5_000_000)
    result = executor.execute_code_blocks([CodeBlock(code="print(dump)", language="python")])

    assert result.exit_code == 0
    assert len(result.output) == MAX_CODE_OUTPUT_CHARS
    assert "output truncated" in result.output


def test_execute_code_blocks_leaves_a_small_stdout_alone():
    from autogen.coding import CodeBlock

    executor = _executor("42\n")
    result = executor.execute_code_blocks([CodeBlock(code="print(42)", language="python")])

    assert result.output == "42\n"


def test_stderr_is_capped_too():
    from autogen.coding import CodeBlock

    executor = _executor("ok\n", stderr="e" * 1_000_000)
    result = executor.execute_code_blocks([CodeBlock(code="pass", language="python")])

    assert result.output.startswith("ok\n")
    assert len(result.output) == MAX_CODE_OUTPUT_CHARS
    assert "output truncated" in result.output
    assert "of 1000012 characters omitted" in result.output


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
