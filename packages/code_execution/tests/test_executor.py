from __future__ import annotations

import os
from pathlib import Path

from code_execution import LocalIPythonBackend


def test_local_backend_applies_cwd_and_env(tmp_path: Path) -> None:
    backend = LocalIPythonBackend(cwd=str(tmp_path), env={"EXECUTOR_TEST": "ok"})
    original_cwd = os.getcwd()
    original_env = os.environ.get("EXECUTOR_TEST")

    result = backend.run_cell(
        "import os\nprint(os.getcwd())\nprint(os.environ.get('EXECUTOR_TEST'))"
    )

    assert result["success"] is True
    lines = [line.strip() for line in result["stdout"].splitlines() if line.strip()]
    assert lines[0] == str(tmp_path)
    assert lines[1] == "ok"
    assert os.getcwd() == original_cwd
    assert os.environ.get("EXECUTOR_TEST") == original_env
