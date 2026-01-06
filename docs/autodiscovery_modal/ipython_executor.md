# Modal IPython Executor

The `autodiscovery_modal.ipython_session` module includes `ModalIPythonBackend`,
which plugs into `code_execution.IPythonExecutor` to run IPython cells on Modal.
Use it when you want the same `IPythonExecutor` interface but executed remotely.

## Public API

- `ModalIPythonBackend`: Backend that invokes the deployed Modal function.

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
