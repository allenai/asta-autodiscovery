from __future__ import annotations

from pathlib import Path

import pytest
from code_execution import ProcessIPythonBackend


@pytest.fixture
def sandbox_backend(tmp_path: Path) -> ProcessIPythonBackend:
    """Backend with a sandbox venv in a temp directory."""
    return ProcessIPythonBackend(
        sandbox_venv_path=str(tmp_path / "sandbox_venv"),
        packages=["numpy"],  # minimal set for faster tests
    )


def test_basic_cell_execution(sandbox_backend: ProcessIPythonBackend) -> None:
    result = sandbox_backend.run_cell("print('hello')")
    assert result["success"] is True
    assert "hello" in result["stdout"]


def test_cwd_and_env(tmp_path: Path) -> None:
    work_dir = tmp_path / "workdir"
    work_dir.mkdir()
    backend = ProcessIPythonBackend(
        cwd=str(work_dir),
        env={"PROC_TEST_VAR": "42"},
        sandbox_venv_path=str(tmp_path / "sandbox_venv"),
        packages=[],
    )
    result = backend.run_cell(
        "import os\nprint(os.getcwd())\nprint(os.environ.get('PROC_TEST_VAR'))"
    )
    assert result["success"] is True
    lines = [line.strip() for line in result["stdout"].splitlines() if line.strip()]
    assert lines[0] == str(work_dir)
    assert lines[1] == "42"


def test_error_handling(sandbox_backend: ProcessIPythonBackend) -> None:
    result = sandbox_backend.run_cell("raise ValueError('boom')")
    assert result["success"] is False
    assert result["error"]["type"] == "ValueError"
    assert "boom" in result["error"]["message"]


def test_timeout(sandbox_backend: ProcessIPythonBackend) -> None:
    result = sandbox_backend.run_cell("import time; time.sleep(60)", timeout_s=1)
    assert result["success"] is False
    assert result["error"]["type"] == "TimeoutError"


def test_isolation_from_host(sandbox_backend: ProcessIPythonBackend) -> None:
    """Verify that the subprocess doesn't share state with the host process."""
    sandbox_backend.run_cell("_test_isolation_var = 123")
    result = sandbox_backend.run_cell("print(_test_isolation_var)")
    assert result["success"] is False


def test_sandbox_has_expected_packages(sandbox_backend: ProcessIPythonBackend) -> None:
    """Verify that the sandbox venv contains packages installed at init."""
    result = sandbox_backend.run_cell("import numpy; print(numpy.__version__)")
    assert result["success"] is True
    assert result["stdout"].strip()  # should print a version string


def test_pip_install_does_not_affect_subsequent_cells(tmp_path: Path) -> None:
    """Verify that per-process pip installs are isolated and don't leak."""
    backend = ProcessIPythonBackend(
        sandbox_venv_path=str(tmp_path / "sandbox_venv"),
        packages=[],
    )
    # Install a small package in one cell via the install-package script
    result = backend.run_cell(
        "import subprocess\n"
        "subprocess.check_call(['install-package', 'six'])\n"
        "import six\n"
        "print(six.__version__)"
    )
    assert result["success"] is True

    # Next cell should NOT see the package (per-process temp dir was cleaned up)
    result2 = backend.run_cell(
        "try:\n"
        "    import six\n"
        "    print('FOUND')\n"
        "except ImportError:\n"
        "    print('NOT_FOUND')\n"
    )
    assert result2["success"] is True
    assert "NOT_FOUND" in result2["stdout"]


def test_sandbox_python_is_not_host_python(tmp_path: Path) -> None:
    """The sandbox python should be different from sys.executable."""
    import sys

    backend = ProcessIPythonBackend(
        sandbox_venv_path=str(tmp_path / "sandbox_venv"),
        packages=[],
    )
    result = backend.run_cell("import sys; print(sys.executable)")
    assert result["success"] is True
    sandbox_py = result["stdout"].strip()
    assert sandbox_py != sys.executable
    assert "sandbox_venv" in sandbox_py
