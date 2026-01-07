# Modal IPython Executor

The `autodiscovery_modal` package provides Modal-backed execution backends that
plug into `code_execution.IPythonExecutor`. Use these when you want the same
`IPythonExecutor` interface but executed remotely, with either Modal Functions
or Modal Sandboxes.

## Public API

- `ModalIPythonBackend`: Backend that invokes the deployed Modal function.
- `ModalSandboxIPythonBackend`: Backend that runs each cell inside a Modal Sandbox
  with dataset mounts scoped per run (recommended for untrusted code).

## Usage Examples

### Basic remote execution

```python
from autodiscovery_modal import ModalIPythonBackend
from code_execution import IPythonExecutor

executor = IPythonExecutor(ModalIPythonBackend())
result = executor.run_cell("print('hello from Modal')")

print(result["stdout"].strip())
print(result["success"])  # True
```

### Sandbox execution with per-run dataset mount (recommended)

```python
from autodiscovery_modal import ModalSandboxIPythonBackend
from code_execution import IPythonExecutor

backend = ModalSandboxIPythonBackend.for_run_dataset(
    app_name="asta-autodiscovery",
    user_id="user-123",
    run_id="forecasting-2026-01-06T120102Z",
    bucket="myapp-datasets",
    key_prefix="users/user-123/runs/forecasting-2026-01-06T120102Z/dataset/",
    read_only=True,  # default; set False to allow writes
    env={"EXPERIMENT_NAME": "forecasting"},
)

executor = IPythonExecutor(backend)
result = executor.run_cell(
    """
import os
from pathlib import Path

root = Path(os.environ["DATASET_ROOT"])
print("USER_ID:", os.environ["USER_ID"])
print("RUN_ID:", os.environ["RUN_ID"])
print("DATASET_ROOT:", root)

for p in sorted(root.rglob("*")):
    if p.is_file():
        print(" -", p.relative_to(root))
"""
)

print(result["stdout"])
print(result["success"])
```

### Sandbox execution with write-enabled dataset mount

```python
from autodiscovery_modal import ModalSandboxIPythonBackend
from code_execution import IPythonExecutor

backend = ModalSandboxIPythonBackend.for_run_dataset(
    app_name="asta-autodiscovery",
    user_id="user-123",
    run_id="experiment-2026-01-06T120102Z",
    bucket="myapp-datasets",
    key_prefix="users/user-123/runs/experiment-2026-01-06T120102Z/dataset/",
    read_only=False,
)

executor = IPythonExecutor(backend)
result = executor.run_cell(
    """
from pathlib import Path
import os

root = Path(os.environ["DATASET_ROOT"])
root.mkdir(parents=True, exist_ok=True)
(root / "note.txt").write_text("hello from sandbox")
print((root / "note.txt").read_text().strip())
"""
)

print(result["stdout"])
print(result["success"])
```

### Target a specific Modal app name

```python
from autodiscovery_modal import ModalIPythonBackend
from code_execution import IPythonExecutor

executor = IPythonExecutor(ModalIPythonBackend(app_name="autodiscovery"))
result = executor.run_cell("print('custom app')")
print(result["stdout"].strip())
```

### Timeout and MIME allowlist

```python
from autodiscovery_modal import ModalIPythonBackend
from code_execution import IPythonExecutor

executor = IPythonExecutor(ModalIPythonBackend())
result = executor.run_cell(
    "import time; time.sleep(5)",
    use_subprocess=True,
    timeout_s=2.0,
    allow_mime=["text/plain"],
)

print(result["success"])  # False
print(result["error"]["type"])  # TimeoutError
```

## Notes

- `ModalIPythonBackend` expects the Modal function to be deployed under the
  configured app name. See `docs/autodiscovery_modal/ipython_session.md` for
  setup and deployment steps.
- Each call is stateless because Modal functions do not keep session state
  between invocations.
- `ModalSandboxIPythonBackend` creates a fresh Sandbox per call and mounts the
  dataset prefix specified by `key_prefix`. This is the safest option for
  untrusted code.
- To authenticate bucket access, pass `bucket_secret` (static credentials) or
  `oidc_auth_role_arn` (OIDC-based IAM role).
- For more detail, see `docs/autodiscovery_modal/sandbox_backend.md`.
