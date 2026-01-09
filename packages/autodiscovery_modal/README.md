# AutoDiscovery Modal

Package for using AutoDiscovery on Modal

## Setup

The following environment variables must be set to use Modal

```sh
export MODAL_TOKEN_ID=
export MODAL_TOKEN_SECRET=
export MODAL_IMAGE_BUILDER_VERSION= # Only required for ephemeral runs or deployments
```

## Code Execution

To test remotely (ephemeral run):

```sh
# Displaying Output
uv run modal run -m autodiscovery_modal.ipython_session::main_print --code-str "print('hi')"

# Without Displaying Output
uv run modal run -m autodiscovery_modal.ipython_session --code-str "print('hi')"
```

Note: `run_ipython_cell` returns a dictionary of outputs but does not print them.
Use `main_print` to emit stdout/stderr and rich outputs in the CLI.

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

To deploy, run the following from the root project:
```sh
just modal-deploy
```
