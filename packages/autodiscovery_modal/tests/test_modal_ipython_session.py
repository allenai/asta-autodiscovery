from __future__ import annotations

import re
from typing import Any

import pytest
from autodiscovery_modal import ipython_session


class _DummySession:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def run_cell(self, code_str: str) -> dict[str, Any]:
        return {
            "code_str": code_str,
            "allow_mime": self.kwargs.get("allow_mime"),
        }


def test_parse_allow_mime_handles_none() -> None:
    assert ipython_session._parse_allow_mime(None) is None


def test_parse_allow_mime_splits_and_strips() -> None:
    value = " text/plain, image/png , ,text/html"
    assert ipython_session._parse_allow_mime(value) == ["text/plain", "image/png", "text/html"]


def test_run_ipython_cell_parses_allow_mime(monkeypatch) -> None:
    monkeypatch.setattr(ipython_session, "IPythonSession", _DummySession)

    result = ipython_session._run_ipython_cell_impl(
        "print('hi')",
        allow_mime="text/plain, image/png",
    )

    assert result["code_str"] == "print('hi')"
    assert result["allow_mime"] == ["text/plain", "image/png"]


def test_lookup_run_ipython_cell_uses_default_app_name(monkeypatch) -> None:
    class _DummyFunction:
        called_with: tuple[str, str] | None = None

        @staticmethod
        def from_name(app_name: str, function_name: str) -> str:
            _DummyFunction.called_with = (app_name, function_name)
            return "handle"

    monkeypatch.setattr(ipython_session.modal, "Function", _DummyFunction)

    result = ipython_session.lookup_run_ipython_cell()

    assert result == "handle"
    assert _DummyFunction.called_with == (
        ipython_session.APP_NAME,
        ipython_session.RUN_IPYTHON_CELL_FUNCTION_NAME,
    )


def test_lookup_run_ipython_cell_accepts_custom_app_name(monkeypatch) -> None:
    class _DummyFunction:
        called_with: tuple[str, str] | None = None

        @staticmethod
        def from_name(app_name: str, function_name: str) -> str:
            _DummyFunction.called_with = (app_name, function_name)
            return "custom-handle"

    monkeypatch.setattr(ipython_session.modal, "Function", _DummyFunction)

    result = ipython_session.lookup_run_ipython_cell("custom-app")

    assert result == "custom-handle"
    assert _DummyFunction.called_with == (
        "custom-app",
        ipython_session.RUN_IPYTHON_CELL_FUNCTION_NAME,
    )


def test_main_entrypoint_invokes_remote(monkeypatch) -> None:
    called_with: dict[str, object] = {}

    def _remote(
        code_str: str,
        *,
        use_subprocess: bool,
        timeout_s: float | None,
        allow_mime: str | None,
        matplotlib_backend: str | None,
    ) -> dict[str, Any]:
        called_with.update(
            {
                "code_str": code_str,
                "use_subprocess": use_subprocess,
                "timeout_s": timeout_s,
                "allow_mime": allow_mime,
                "matplotlib_backend": matplotlib_backend,
            }
        )
        return {"ok": True}

    monkeypatch.setattr(ipython_session.run_ipython_cell, "remote", _remote)

    result = ipython_session.main(
        "print('hello')",
        use_subprocess=True,
        timeout_s=1.5,
        allow_mime="text/plain",
        matplotlib_backend="inline",
    )

    assert result == {"ok": True}
    assert called_with == {
        "code_str": "print('hello')",
        "use_subprocess": True,
        "timeout_s": 1.5,
        "allow_mime": "text/plain",
        "matplotlib_backend": "inline",
    }


@pytest.mark.modal
def test_run_ipython_cell_remote_deployed_executes() -> None:
    function = ipython_session.lookup_run_ipython_cell()
    result = function.remote("print('hello')\n1 + 1")

    assert result["success"] is True
    assert result["stdout"].strip() == "hello\nOut[0]: 2"
    assert result["error"] is None


@pytest.mark.modal
def test_run_ipython_cell_remote_ephemeralexecutes() -> None:
    with ipython_session.app.run():
        result = ipython_session.run_ipython_cell.remote("print('hello')\n1 + 1")

    assert result["success"] is True
    assert result["stdout"].strip() == "hello\nOut[0]: 2"
    assert result["error"] is None


@pytest.mark.modal
def test_run_ipython_cell_remote_requests_not_installed_by_default() -> None:
    function = ipython_session.lookup_run_ipython_cell()
    result = function.remote("import requests\nprint(requests.__version__)")

    assert result["success"] is False
    assert result["error"] is not None
    assert result["error"]["type"] == "ModuleNotFoundError"


@pytest.mark.modal
def test_run_ipython_cell_remote_can_install_requests_with_pip_magic() -> None:
    function = ipython_session.lookup_run_ipython_cell()
    code_str = "%pip install requests\nimport requests\nprint(\"requests\")\nprint(requests.__version__)"
    result = function.remote(code_str)

    assert result["success"] is True
    lines = [line.strip() for line in result["stdout"].splitlines() if line.strip()]
    assert lines[-2] == "requests"
    assert re.match(r"^\d+\.\d+\.\d+(?:\.\d+)?$", lines[-1])
