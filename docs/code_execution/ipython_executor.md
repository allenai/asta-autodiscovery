# IPython Executor

The `code_execution.executor` module provides a small facade around IPython cell
execution. It lets you swap execution backends (local, remote, mocked) without
changing the call sites. The executor returns the same output schema as
`IPythonSession`.

`autodiscovery_modal` ships `ModalSandboxIPythonBackend` which plugs into
`IPythonExecutor` for sandbox-isolated execution. See
`docs/autodiscovery_modal/ipython_executor.md` for details.

## Public API

- `IPythonBackend`: Protocol that defines `run_cell`.
- `LocalIPythonBackend`: Stateless local backend that creates a new
  `IPythonSession` for each call.
- `IPythonExecutor`: Facade that delegates execution to the configured backend.

## Usage Examples

### Basic local execution

```python
from code_execution import IPythonExecutor, LocalIPythonBackend

executor = IPythonExecutor(LocalIPythonBackend())
result = executor.run_cell("print('hello')\n1 + 1")

print(result["stdout"].strip())  # hello
print(result["success"])  # True
```

### Local execution with a working directory and env vars

```python
from code_execution import IPythonExecutor, LocalIPythonBackend

backend = LocalIPythonBackend(
    cwd="/tmp",
    env={"DATASET_ROOT": "/tmp/data"},
)
executor = IPythonExecutor(backend)
result = executor.run_cell(
    "import os; print(os.getcwd()); print(os.environ['DATASET_ROOT'])"
)

print(result["stdout"].strip())
```

### Persistent state across calls

`LocalIPythonBackend` starts a new IPython session per call. Use a custom backend
if you want state to persist across multiple executions.

```python
from code_execution import IPythonExecutor
from code_execution.ipython_session import IPythonSession


class StatefulBackend:
    """Backend that keeps a single IPython session alive."""

    def __init__(self) -> None:
        """Initialize the backend with a persistent session."""
        self._session = IPythonSession()

    def run_cell(self, code_str: str, **kwargs: object) -> dict[str, object]:
        """Execute code in the persistent session.

        Args:
            code_str: Code to execute in the session.
            **kwargs: Ignored execution options for protocol compatibility.

        Returns:
            Execution output bundle.
        """
        return self._session.run_cell(code_str)


executor = IPythonExecutor(StatefulBackend())
executor.run_cell("value = 41")
result = executor.run_cell("value += 1; print(value)")
print(result["stdout"].strip())  # 42
```

### Subprocess execution with a timeout

```python
from code_execution import IPythonExecutor, LocalIPythonBackend

executor = IPythonExecutor(LocalIPythonBackend())
result = executor.run_cell(
    "import time; time.sleep(5)",
    use_subprocess=True,
    timeout_s=2.0,
)

print(result["success"])  # False
print(result["error"]["type"])  # TimeoutError
```

### Backend injection for tests

```python
from code_execution import IPythonExecutor


class FakeBackend:
    """Backend used to assert calls without running IPython."""

    def __init__(self) -> None:
        """Initialize the fake backend call tracker."""
        self.calls: list[str] = []

    def run_cell(self, code_str: str, **kwargs: object) -> dict[str, object]:
        """Return a successful response and record the call.

        Args:
            code_str: Code string passed to the backend.
            **kwargs: Ignored execution options for protocol compatibility.

        Returns:
            Stubbed execution output bundle.
        """
        self.calls.append(code_str)
        return {"stdout": "", "stderr": "", "rich_outputs": [], "success": True, "error": None}


backend = FakeBackend()
executor = IPythonExecutor(backend)
executor.run_cell("print('noop')")
assert backend.calls == ["print('noop')"]
```
