"""Tests for the cap on code-executor output size.

Generated code regularly prints an entire dataset; the executor's output becomes a
chat message that is re-serialized into every later LLM request, so an uncapped
output OOM-kills the job (observed: 676 MB of stdout, container SIGKILLed).
"""

import pytest

from autodiscovery.agents import (
    DEFAULT_MAX_CODE_OUTPUT_CHARS,
    ModalSandboxExecutor,
    _truncate_output,
)


def test_short_output_is_returned_verbatim():
    assert _truncate_output("hello", 100) == "hello"


def test_output_at_the_limit_is_not_truncated():
    output = "x" * 100
    assert _truncate_output(output, 100) == output


def test_non_positive_limit_disables_truncation():
    output = "x" * 10_000
    assert _truncate_output(output, 0) == output
    assert _truncate_output(output, -1) == output


def test_long_output_keeps_both_ends_and_reports_the_drop():
    output = "H" * 5_000 + "M" * 90_000 + "T" * 5_000
    truncated = _truncate_output(output, 10_000)

    assert truncated.startswith("H")
    assert truncated.endswith("T")
    assert "output truncated" in truncated
    # 90k characters omitted out of 100k, and the middle is gone.
    assert "90000 of 100000 characters omitted" in truncated
    assert "M" not in truncated
    # The notice adds a bounded amount on top of the limit.
    assert len(truncated) < 10_000 + 500


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

    executor = _executor("x" * 5_000_000, max_output_chars=50_000)
    result = executor.execute_code_blocks([CodeBlock(code="print(dump)", language="python")])

    assert result.exit_code == 0
    assert len(result.output) < 51_000
    assert "output truncated" in result.output


def test_execute_code_blocks_leaves_a_small_stdout_alone():
    from autogen.coding import CodeBlock

    executor = _executor("42\n")
    result = executor.execute_code_blocks([CodeBlock(code="print(42)", language="python")])

    assert result.output == "42\n"


def test_limit_comes_from_the_environment_then_the_default(monkeypatch):
    monkeypatch.setenv("AUTODISCOVERY_MAX_CODE_OUTPUT_CHARS", "1234")
    assert _executor("")._max_output_chars == 1234

    monkeypatch.delenv("AUTODISCOVERY_MAX_CODE_OUTPUT_CHARS")
    assert _executor("")._max_output_chars == DEFAULT_MAX_CODE_OUTPUT_CHARS

    # An explicit argument wins over the environment.
    monkeypatch.setenv("AUTODISCOVERY_MAX_CODE_OUTPUT_CHARS", "1234")
    assert _executor("", max_output_chars=99)._max_output_chars == 99


def test_stderr_is_capped_too():
    from autogen.coding import CodeBlock

    executor = _executor("ok\n", stderr="e" * 1_000_000, max_output_chars=20_000)
    result = executor.execute_code_blocks([CodeBlock(code="pass", language="python")])

    assert result.output.startswith("ok\n")
    assert len(result.output) < 41_000
    assert "output truncated" in result.output


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__]))
