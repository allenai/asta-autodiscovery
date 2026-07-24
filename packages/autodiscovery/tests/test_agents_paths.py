"""Tests for the code-execution working-dir handling in agents.py.

Guards the process/local vs modal path translation: the code transform injects
`os.chdir(working_dir)` into every cell, and the process/local subprocess
already starts with cwd=work_dir, so that injected path must be absolute or it
stacks (work_dir/work_dir) and fails with FileNotFoundError.
"""

from __future__ import annotations

import json
import os

from autodiscovery.agents import SimpleCodeBlockTransform, code_transform_working_dir


def test_working_dir_modal_uses_mount_path() -> None:
    assert code_transform_working_dir("modal", "work", "/data") == "/data"


def test_working_dir_process_is_absolute() -> None:
    result = code_transform_working_dir("process", "work", None)
    assert os.path.isabs(result)
    assert result == os.path.abspath("work")


def test_working_dir_local_is_absolute() -> None:
    result = code_transform_working_dir("local", "some/rel/work", None)
    assert os.path.isabs(result)
    assert result == os.path.abspath("some/rel/work")


def test_transform_injects_absolute_chdir() -> None:
    transform = SimpleCodeBlockTransform(working_dir="/app/work")
    messages = [{"content": json.dumps({"code": "x = 1\nprint(x)"})}]

    out = transform.apply_transform(messages)
    content = out[-1]["content"]

    assert "os.chdir('/app/work')" in content
    # The user code is preserved after the injected chdir.
    assert "print(x)" in content
    assert content.index("os.chdir(") < content.index("print(x)")


def test_transform_and_working_dir_compose_to_absolute() -> None:
    # End-to-end of the fix: process backend -> absolute dir -> absolute chdir,
    # so it never stacks relative to the subprocess's own cwd.
    working_dir = code_transform_working_dir("process", "work", None)
    transform = SimpleCodeBlockTransform(working_dir=working_dir)
    content = transform.apply_transform([{"content": json.dumps({"code": "pass"})}])[-1][
        "content"
    ]
    assert f"os.chdir('{os.path.abspath('work')}')" in content
