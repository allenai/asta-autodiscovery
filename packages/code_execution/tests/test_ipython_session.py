from __future__ import annotations

import base64
import uuid
import zipfile
from pathlib import Path

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
    assert any("image/png" in bundle and bundle["image/png"] for bundle in outputs["rich_outputs"])


def test_matplotlib_formats_respect_allow_mime() -> None:
    default_session = IPythonSession()
    code = """
import matplotlib.pyplot as plt

plt.plot([0, 1], [0, 1])
plt.show()
"""
    default_outputs = default_session.run_cell(code)

    assert default_outputs["success"] is True
    assert any(
        {"image/png", "image/svg+xml", "image/jpeg"}.issubset(bundle.keys())
        for bundle in default_outputs["rich_outputs"]
    )

    png_only_session = IPythonSession(allow_mime=["image/png"])
    png_only_outputs = png_only_session.run_cell(code)

    assert png_only_outputs["success"] is True
    assert png_only_outputs["rich_outputs"]
    assert all(bundle.keys() == {"image/png"} for bundle in png_only_outputs["rich_outputs"])


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
    assert _normalize_value({1: b"hi"}) == {"1": base64.b64encode(b"hi").decode("ascii")}

    bundle = _normalize_mime_bundle(
        {"text/plain": "ok", "text/html": "<b>no</b>"},
        frozenset({"text/plain"}),
    )
    assert bundle == {"text/plain": "ok"}


def _build_wheel(tmp_path: Path, package_name: str, version: str = "0.0.0") -> Path:
    module_dir = tmp_path / package_name
    module_dir.mkdir(parents=True)
    (module_dir / "__init__.py").write_text(
        "\n".join(
            [
                f'__version__ = "{version}"',
                "VALUE = 42",
                "",
            ]
        ),
        encoding="utf-8",
    )

    dist_info = f"{package_name}-{version}.dist-info"
    dist_dir = tmp_path / dist_info
    dist_dir.mkdir(parents=True)
    (dist_dir / "METADATA").write_text(
        "\n".join(
            [
                "Metadata-Version: 2.1",
                f"Name: {package_name}",
                f"Version: {version}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (dist_dir / "WHEEL").write_text(
        "\n".join(
            [
                "Wheel-Version: 1.0",
                "Generator: ipython-session-tests",
                "Root-Is-Purelib: true",
                "Tag: py3-none-any",
                "",
            ]
        ),
        encoding="utf-8",
    )

    wheel_name = f"{package_name}-{version}-py3-none-any.whl"
    wheel_path = tmp_path / wheel_name

    record_rows: list[tuple[str, int]] = []
    with zipfile.ZipFile(wheel_path, "w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for file_path in module_dir.rglob("*"):
            if file_path.is_file():
                arcname = f"{package_name}/{file_path.name}"
                zip_file.write(file_path, arcname)
                record_rows.append((arcname, file_path.stat().st_size))
        for file_path in dist_dir.rglob("*"):
            if file_path.is_file():
                arcname = f"{dist_info}/{file_path.name}"
                zip_file.write(file_path, arcname)
                record_rows.append((arcname, file_path.stat().st_size))

        record_name = f"{dist_info}/RECORD"
        record_lines = [f"{path},,{size}" for path, size in record_rows]
        record_lines.append(f"{record_name},,")
        zip_file.writestr(record_name, "\n".join(record_lines))

    return wheel_path


@pytest.mark.filterwarnings(r"ignore:.*forkpty\(\).*deadlocks.*:DeprecationWarning:pty")
def test_ipython_session_can_install_local_wheel_with_pip_magic(tmp_path: Path) -> None:
    session = IPythonSession()
    package_name = f"pip_magic_demo_{uuid.uuid4().hex}"
    wheel_path = _build_wheel(tmp_path, package_name)
    code = (
        f'%pip install "{wheel_path}"\n'
        f"import {package_name}\n"
        f'print("{package_name}")\n'
        f"print({package_name}.__version__)"
    )
    outputs = session.run_cell(code)

    assert outputs["success"] is True
    lines = [line.strip() for line in outputs["stdout"].splitlines() if line.strip()]
    assert lines[-2] == package_name
    assert lines[-1] == "0.0.0"
