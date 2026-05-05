# AutoDiscovery Modal

Package for using AutoDiscovery on Modal

## Setup

The following environment variables must be set to use Modal

```sh
export MODAL_TOKEN_ID=
export MODAL_TOKEN_SECRET=
export MODAL_IMAGE_BUILDER_VERSION= # Only required for ephemeral sandbox runs
```

## Sandbox Executor

Use the Sandbox backend when you need per-run dataset mounts and strong isolation
for untrusted code.

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
result = executor.run_cell("print('hello from sandbox')")
print(result["stdout"])
```
