from __future__ import annotations

import base64

import pytest
from code_execution.ipython_session import (
    IPythonSession,
    _normalize_mime_bundle,
    _normalize_value,
)


def test_run_cell_captures_stdout() -> None:
    session = IPythonSession()
    outputs = session.run_cell('print("hello")')

    assert outputs["success"] is True
    assert outputs["stdout"].strip() == "hello"
    assert outputs["error"] is None


def test_run_cell_captures_error() -> None:
    session = IPythonSession()
    outputs = session.run_cell("1/0")

    assert outputs["success"] is False
    assert outputs["error"]["type"] == "ZeroDivisionError"
    assert "ZeroDivisionError" in outputs["error"]["traceback"]


def test_run_cell_captures_rich_outputs() -> None:
    session = IPythonSession()
    code = """
import matplotlib.pyplot as plt

plt.plot([0, 1], [0, 1])
plt.show()
"""
    outputs = session.run_cell(code)

    assert outputs["success"] is True
    assert any(
        "image/png" in bundle and bundle["image/png"] for bundle in outputs["rich_outputs"]
    )


def test_run_cell_subprocess_success() -> None:
    session = IPythonSession(use_subprocess=True, timeout_s=2.0)
    outputs = session.run_cell("x = 3; print(x)")

    assert outputs["success"] is True
    assert outputs["stdout"].strip() == "3"
    assert outputs["error"] is None


def test_timeout_requires_subprocess() -> None:
    session = IPythonSession(timeout_s=0.1)
    with pytest.raises(ValueError):
        session.run_cell("print('nope')")


def test_subprocess_timeout() -> None:
    session = IPythonSession(use_subprocess=True, timeout_s=0.2)
    outputs = session.run_cell("import time; time.sleep(1)")

    assert outputs["success"] is False
    assert outputs["error"]["type"] == "TimeoutError"


def test_run_cell_persists_state_across_calls() -> None:
    session = IPythonSession()
    session.run_cell("value = 41")
    outputs = session.run_cell("value += 1; print(value)")

    assert outputs["success"] is True
    assert outputs["stdout"].strip() == "42"


def test_run_cell_captures_stderr() -> None:
    session = IPythonSession()
    outputs = session.run_cell("import sys; print('boom', file=sys.stderr)")

    assert outputs["success"] is True
    assert outputs["stderr"].strip() == "boom"


def test_allow_mime_filters_outputs() -> None:
    session = IPythonSession(allow_mime={"text/plain"})
    code = """
from IPython.display import HTML, display
display(HTML("<b>hi</b>"))
"""
    outputs = session.run_cell(code)

    assert outputs["success"] is True
    assert outputs["rich_outputs"]
    assert all("text/html" not in bundle for bundle in outputs["rich_outputs"])


def test_normalize_helpers() -> None:
    assert _normalize_value(b"hi") == base64.b64encode(b"hi").decode("ascii")
    assert _normalize_value({1: b"hi"}) == {
        "1": base64.b64encode(b"hi").decode("ascii")
    }

    bundle = _normalize_mime_bundle(
        {"text/plain": "ok", "text/html": "<b>no</b>"},
        frozenset({"text/plain"}),
    )
    assert bundle == {"text/plain": "ok"}
