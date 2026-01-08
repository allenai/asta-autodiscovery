# Modal Sandbox Backend

`autodiscovery_modal.sandbox_backend` provides a Modal Sandbox-based execution
backend that plugs into `code_execution.IPythonExecutor`. It creates a fresh
Sandbox per call, mounts a dataset prefix into the Sandbox filesystem, and then
executes the IPython cell inside the container. This is the safest approach for
LLM-generated or otherwise untrusted code.

## Public API

- `ModalSandboxIPythonBackend`: Sandbox-backed `IPythonExecutor` backend.

## Usage Examples

### Basic execution with a per-run dataset mount (read-only by default)

```python
from autodiscovery_modal import ModalSandboxIPythonBackend
from code_execution import IPythonExecutor

backend = ModalSandboxIPythonBackend.for_run_dataset(
    app_name="asta-autodiscovery",
    user_id="user-123",
    run_id="forecasting-2026-01-06T120102Z",
    bucket="myapp-datasets",
    key_prefix="users/user-123/runs/forecasting-2026-01-06T120102Z/dataset/",
    read_only=True,
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

### Execution with a generic bucket prefix (no user/run metadata)

```python
from autodiscovery_modal import ModalSandboxIPythonBackend
from code_execution import IPythonExecutor

backend = ModalSandboxIPythonBackend.for_bucket_prefix(
    app_name="asta-autodiscovery",
    bucket="myapp-datasets",
    key_prefix="samples/",
    read_only=True,
    env={"EXPERIMENT_NAME": "smoke-test"},
)

executor = IPythonExecutor(backend)
result = executor.run_cell("import os; print(os.environ['DATASET_ROOT'])")

print(result["stdout"].strip())
print(result["success"])
```

### Write-enabled dataset mounts

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

### Adding environment variables

```python
from autodiscovery_modal import ModalSandboxIPythonBackend
from code_execution import IPythonExecutor

backend = ModalSandboxIPythonBackend.for_run_dataset(
    app_name="asta-autodiscovery",
    user_id="user-123",
    run_id="forecasting-2026-01-06T120102Z",
    bucket="myapp-datasets",
    key_prefix="users/user-123/runs/forecasting-2026-01-06T120102Z/dataset/",
    env={"EXPERIMENT_NAME": "forecasting"},
)

executor = IPythonExecutor(backend)
result = executor.run_cell("import os; print(os.environ['EXPERIMENT_NAME'])")

print(result["stdout"].strip())
```

## Notes

- Each call creates a fresh Sandbox. This prevents untrusted code from
  inspecting other runs, and avoids cross-run leakage.
- `key_prefix` must end with `/`. The backend normalizes prefixes automatically.
- Use `for_bucket_prefix` when you want a generic storage prefix without user/run metadata.
- For S3-compatible services (e.g., GCS), pass `bucket_endpoint_url` so Modal mounts the right endpoint.
- For bucket authentication, pass `bucket_secret` (static credentials) or
  `oidc_auth_role_arn` (OIDC-based IAM role).
- Sandboxes default to a 10-minute lifetime. Override with `sandbox_timeout_s`
  if you need longer-running executions.
