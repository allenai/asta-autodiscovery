# IPython Session

The `code_execution.ipython_session` module provides a lightweight wrapper around
IPython's `InteractiveShell` for executing code strings and collecting a
structured output bundle. It supports in-process execution for stateful
sessions and an optional subprocess mode that enables hard timeouts.

## Overview

Key responsibilities:

- Run code strings through IPython and capture stdout, stderr, rich display data,
  and error details.
- Normalize outputs into JSON-safe values for downstream serialization.
- Optionally run each cell in a separate subprocess with a hard timeout.
- Configure display formatters and matplotlib backends for consistent rich output.

## Public API

### `ExecutionConfig`

`ExecutionConfig` is a frozen dataclass that defines how an IPython session
should execute cells.

Fields:

- `use_subprocess` (bool): When `True`, each cell runs in a separate process.
- `timeout_s` (float | None): Hard timeout in seconds when `use_subprocess=True`.
- `allow_mime` (frozenset[str]): MIME types to retain from rich display output.
- `matplotlib_backend` (str | None): Backend string passed to matplotlib.

### `IPythonSession`

`IPythonSession` owns a persistent IPython shell instance and provides a single
public method for execution.

Constructor arguments:

- `use_subprocess` (bool): Enable subprocess isolation for cell execution.
- `timeout_s` (float | None): Hard timeout (requires `use_subprocess=True`).
- `allow_mime` (Iterable[str] | None): Custom MIME allowlist.
- `matplotlib_backend` (str | None): Override matplotlib backend configuration.

Method:

- `run_cell(code_str: str) -> dict[str, Any]`: Execute the provided code string
  and return a structured output bundle.

If `timeout_s` is set while `use_subprocess=False`, `run_cell` raises a
`ValueError` because an in-process IPython run cannot be hard-stopped.

## Output Schema

`run_cell` returns a dictionary with the following shape:

- `stdout` (str): Captured stdout during execution.
- `stderr` (str): Captured stderr during execution.
- `rich_outputs` (list[dict[str, Any]]): A list of MIME bundles corresponding to
  display outputs.
- `success` (bool): Whether IPython reports successful execution.
- `error` (dict[str, str] | None): Error details when execution fails.

Error details include:

- `type`: Exception class name.
- `message`: Exception message.
- `traceback`: Formatted traceback string.

On subprocess timeout, the error payload has `type` set to `TimeoutError` with
an empty `traceback` and `success` set to `False`.

## MIME Handling

Rich display outputs are filtered to an allowlist defined by `allow_mime`.
Unsupported MIME entries are dropped to prevent unexpected payloads. Values are
normalized so they are JSON-safe:

- `bytes` are base64-encoded to ASCII strings.
- Lists, tuples, and dicts are recursively normalized.
- Other objects fall back to `repr`.

Default MIME allowlist:

- `text/plain`
- `text/html`
- `text/markdown`
- `text/latex`
- `image/png`
- `image/svg+xml`
- `image/jpeg`
- `application/json`
- `application/javascript`
- `application/pdf`

## Matplotlib Integration

When `matplotlib_backend` is set, the module attempts to configure matplotlib
for non-interactive rendering. If the backend includes
`matplotlib_inline.backend_inline`, the module sets output formats based on the
`allow_mime` allowlist (PNG, SVG, JPEG). Failures during configuration are
silently ignored to avoid breaking execution in environments where matplotlib
is unavailable or already initialized.

## Subprocess Isolation and Timeouts

With `use_subprocess=True`, each call to `run_cell` is executed in a child
process created with the `spawn` start method. This enables a hard timeout by
terminating the process if it exceeds `timeout_s`.

Trade-offs of subprocess mode:

- Each run starts a new IPython instance, so state is not preserved across calls.
- Spawned processes are more expensive than in-process execution.
- Timeouts are enforced reliably because the parent can terminate the child.

## Usage Examples

Basic in-process execution:

```python
from code_execution.ipython_session import IPythonSession

session = IPythonSession()
result = session.run_cell("print('hello')\n1 + 1")
print(result["stdout"])
print(result["success"])
```

Subprocess execution with a timeout:

```python
from code_execution.ipython_session import IPythonSession

session = IPythonSession(use_subprocess=True, timeout_s=2.0)
result = session.run_cell("import time; time.sleep(5)")
print(result["success"])  # False
print(result["error"]["type"])  # TimeoutError
```

Custom MIME allowlist (only png):

```python
from code_execution.ipython_session import IPythonSession

session = IPythonSession(allow_mime=["image/png"])
result = session.run_cell("import matplotlib.pyplot as plt; plt.plot([1,2,3], [4,5,6]); plt.show()")
print(result["rich_outputs"])
```
