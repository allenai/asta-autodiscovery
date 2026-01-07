from __future__ import annotations

import json
from typing import Any

from autodiscovery_modal import sandbox_backend


class _DummyStream:
    def __init__(self, payload: str | bytes) -> None:
        self._payload = payload

    def read(self) -> str | bytes:
        return self._payload


class _DummyStdin:
    def __init__(self) -> None:
        self.buffer: bytes = b""
        self.eof = False

    def write(self, data: bytes) -> None:
        self.buffer += data

    def write_eof(self) -> None:
        self.eof = True

    def drain(self) -> None:
        return None


class _DummyProcess:
    def __init__(self, stdout: str | bytes, stderr: str | bytes) -> None:
        self.stdin = _DummyStdin()
        self.stdout = _DummyStream(stdout)
        self.stderr = _DummyStream(stderr)
        self.waited = False

    def wait(self) -> None:
        self.waited = True


class _DummySandbox:
    def __init__(self, process: _DummyProcess) -> None:
        self._process = process
        self.exec_args: tuple[Any, ...] | None = None
        self.exec_kwargs: dict[str, Any] | None = None
        self.terminated = False

    def exec(self, *args: Any, **kwargs: Any) -> _DummyProcess:
        self.exec_args = args
        self.exec_kwargs = kwargs
        return self._process

    def terminate(self) -> None:
        self.terminated = True


def test_sandbox_backend_creates_mount_and_passes_env(monkeypatch) -> None:
    created_mount: dict[str, Any] = {}
    created_secret: dict[str, Any] = {}
    sandbox_create_kwargs: dict[str, Any] = {}

    def _dummy_mount(**kwargs: Any) -> dict[str, Any]:
        created_mount.update(kwargs)
        return {"mount": kwargs}

    def _dummy_secret_from_dict(payload: dict[str, str]) -> dict[str, str]:
        created_secret.update(payload)
        return {"secret": payload}

    def _dummy_app_lookup(app_name: str, *, create_if_missing: bool) -> str:
        return f"app:{app_name}:{create_if_missing}"

    def _dummy_sandbox_create(*, app: Any, image: Any, volumes: dict[str, Any], secrets: list[Any], timeout: int) -> _DummySandbox:
        sandbox_create_kwargs.update(
            {
                "app": app,
                "image": image,
                "volumes": volumes,
                "secrets": secrets,
                "timeout": timeout,
            }
        )
        result_payload = {"stdout": "ok", "stderr": "", "rich_outputs": [], "success": True, "error": None}
        process = _DummyProcess(stdout=json.dumps(result_payload), stderr="")
        return _DummySandbox(process)

    monkeypatch.setattr(sandbox_backend.modal, "CloudBucketMount", _dummy_mount)
    monkeypatch.setattr(
        sandbox_backend.modal,
        "Secret",
        type("_Secret", (), {"from_dict": staticmethod(_dummy_secret_from_dict)}),
    )
    monkeypatch.setattr(
        sandbox_backend.modal, "App", type("_App", (), {"lookup": staticmethod(_dummy_app_lookup)})
    )
    monkeypatch.setattr(
        sandbox_backend.modal,
        "Sandbox",
        type("_Sandbox", (), {"create": staticmethod(_dummy_sandbox_create)}),
    )

    backend = sandbox_backend.ModalSandboxIPythonBackend.for_run_dataset(
        app_name="demo-app",
        user_id="user-1",
        run_id="run-1",
        bucket="my-bucket",
        key_prefix="users/user-1/runs/run-1/dataset",
        mount_path="/data",
        read_only=True,
        env={"EXTRA": "value"},
    )

    result = backend.run_cell("print('hello')", allow_mime=["text/plain"])

    assert created_mount["bucket_name"] == "my-bucket"
    assert created_mount["key_prefix"].endswith("/")
    assert created_mount["read_only"] is True
    assert sandbox_create_kwargs["volumes"]["/data"] == {"mount": created_mount}
    assert created_secret["USER_ID"] == "user-1"
    assert created_secret["RUN_ID"] == "run-1"
    assert created_secret["DATASET_ROOT"] == "/data"
    assert created_secret["EXTRA"] == "value"
    assert result["success"] is True


def test_sandbox_backend_writes_payload_and_terminates(monkeypatch) -> None:
    process = _DummyProcess(
        stdout=json.dumps(
            {"stdout": "", "stderr": "", "rich_outputs": [], "success": True, "error": None}
        ),
        stderr=b"",
    )
    sandbox = _DummySandbox(process)
    captured_secret: dict[str, str] = {}

    def _dummy_sandbox_create(*, app: Any, image: Any, volumes: dict[str, Any], secrets: list[Any], timeout: int) -> _DummySandbox:
        return sandbox

    monkeypatch.setattr(
        sandbox_backend.modal,
        "Sandbox",
        type("_Sandbox", (), {"create": staticmethod(_dummy_sandbox_create)}),
    )
    monkeypatch.setattr(
        sandbox_backend.modal,
        "App",
        type("_App", (), {"lookup": staticmethod(lambda app_name, *, create_if_missing: app_name)}),
    )
    monkeypatch.setattr(sandbox_backend.modal, "CloudBucketMount", lambda **_: {"mount": "ok"})
    monkeypatch.setattr(
        sandbox_backend.modal,
        "Secret",
        type("_Secret", (), {"from_dict": staticmethod(lambda payload: captured_secret.update(payload) or payload)}),
    )

    backend = sandbox_backend.ModalSandboxIPythonBackend(
        app_name="demo-app",
        bucket_mount={"mount": "ok"},
        env={"USER_ID": "user-1", "RUN_ID": "run-1", "DATASET_ROOT": "/data"},
    )

    backend.run_cell("print('hello')", allow_mime=["text/plain"], timeout_s=3.0)

    payload = json.loads(process.stdin.buffer.decode("utf-8"))
    assert payload["code_str"] == "print('hello')"
    assert payload["allow_mime"] == ["text/plain"]
    assert payload["timeout_s"] == 3.0
    assert process.stdin.eof is True
    assert sandbox.terminated is True
    assert captured_secret["DATASET_ROOT"] == "/data"


def test_sandbox_backend_returns_error_on_invalid_json(monkeypatch) -> None:
    process = _DummyProcess(stdout="not-json", stderr="bad")
    sandbox = _DummySandbox(process)

    def _dummy_sandbox_create(*, app: Any, image: Any, volumes: dict[str, Any], secrets: list[Any], timeout: int) -> _DummySandbox:
        return sandbox

    monkeypatch.setattr(
        sandbox_backend.modal,
        "Sandbox",
        type("_Sandbox", (), {"create": staticmethod(_dummy_sandbox_create)}),
    )
    monkeypatch.setattr(
        sandbox_backend.modal,
        "App",
        type("_App", (), {"lookup": staticmethod(lambda app_name, *, create_if_missing: app_name)}),
    )
    monkeypatch.setattr(sandbox_backend.modal, "CloudBucketMount", lambda **_: {"mount": "ok"})

    backend = sandbox_backend.ModalSandboxIPythonBackend(
        app_name="demo-app",
        bucket_mount={"mount": "ok"},
    )

    result = backend.run_cell("print('hello')")

    assert result["success"] is False
    assert result["stderr"] == "bad"
    assert result["error"]["type"] == "RuntimeError"
