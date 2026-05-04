# Modal IPython Executor

The `autodiscovery_modal` package provides a Modal Sandbox-based execution backend
that plugs into `code_execution.IPythonExecutor`. Use it when you want per-run
dataset mounts and strong isolation for untrusted code.

## Public API

- `ModalSandboxIPythonBackend`: Backend that runs each cell inside a fresh Modal
  Sandbox with dataset mounts scoped per run.

## Usage Examples

### Sandbox execution with per-run dataset mount

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

### Sandbox execution with a generic bucket prefix

```python
from autodiscovery_modal import ModalSandboxIPythonBackend
from code_execution import IPythonExecutor

backend = ModalSandboxIPythonBackend.for_bucket_prefix(
    app_name="asta-autodiscovery",
    bucket="myapp-datasets",
    key_prefix="samples/",
    read_only=True,
)

executor = IPythonExecutor(backend)
result = executor.run_cell("import os; print(os.environ['DATASET_ROOT'])")

print(result["stdout"].strip())
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

## Notes

- Each call creates a fresh Sandbox and mounts the dataset prefix specified by
  `key_prefix`. This provides strong isolation for untrusted code.
- Use `for_bucket_prefix` when you want a generic storage prefix without user/run metadata.
- For S3-compatible services (e.g., GCS), pass `bucket_endpoint_url` so Modal mounts the right endpoint.
- To authenticate bucket access, pass `bucket_secret` (static credentials) or
  `oidc_auth_role_arn` (OIDC-based IAM role).
- For more detail, see `docs/autodiscovery_modal/sandbox_backend.md`.
