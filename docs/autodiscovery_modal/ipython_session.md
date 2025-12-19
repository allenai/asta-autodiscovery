# Modal IPython Session

The `autodiscovery_modal.ipython_session` module provides Modal-hosted access to
the same IPython execution workflow used by the in-process
`code_execution.ipython_session` module. It exposes a stateless Modal function
that executes a single cell and returns normalized outputs.

## Overview

Key responsibilities:

- Package the IPython execution dependencies inside a Modal image.
- Expose a Modal function that runs one code cell per invocation.
- Parse scalar Modal CLI inputs (CSV allowlist) into rich configuration.
- Provide a lookup helper for connecting to a deployed function.

## Setup

Modal requires the following environment variables to be set:

- `MODAL_TOKEN_ID`
- `MODAL_TOKEN_SECRET`
- `MODAL_IMAGE_BUILDER_VERSION` (only required for ephemeral runs or deployments)

## Remote Execution

Ephemeral run using the Modal CLI:

```bash
uv run modal run -m autodiscovery_modal.ipython_session::app.run_ipython_cell --code-str "print('hi')"
```

Deploy the Modal app from the repository root:

```bash
modal-deploy
```

## Usage Examples

Ephemeral execution (no deployment required):

```python
from autodiscovery_modal import ipython_session

with ipython_session.app.run():
        result = ipython_session.run_ipython_cell.remote("print('hello')\n1 + 1")

print(result["stdout"])
```

Deployed execution (invoke an already deployed function from Python):

```python
from autodiscovery_modal.ipython_session import lookup_run_ipython_cell

remote = lookup_run_ipython_cell()
result = remote.remote("print('hello from deployed Modal')")
print(result["stdout"])
```

## Public API

### `run_ipython_cell`

`run_ipython_cell` is the Modal function entrypoint that executes a single code
cell and returns a normalized output bundle (stdout, stderr, rich outputs,
success, error details).

### `lookup_run_ipython_cell`

`lookup_run_ipython_cell` returns a `modal.Function` handle for a deployed app
so you can invoke the function without importing the module into the caller
runtime.
