"""Stateless IPython execution helpers for use in Modal functions."""

from collections.abc import Iterable
from typing import Any

import modal
from code_execution.ipython_session import ExecutionConfig, IPythonSession

APP_NAME = "autodiscovery"
RUN_IPYTHON_CELL_FUNCTION_NAME = "run_ipython_cell"

app = modal.App(APP_NAME)
image = (
    modal.Image.debian_slim(python_version="3.13")
    .uv_pip_install("ipython>=9.8.0")
    .add_local_python_source("code_execution")
)


def _parse_allow_mime(allow_mime: str | None) -> list[str] | None:
    # Modal CLI only supports scalar parameter types, so we accept a CSV string.
    if not allow_mime:
        return None
    return [item.strip() for item in allow_mime.split(",") if item.strip()]


class ModalIPythonBackend:
    """Backend that executes IPython cells via a Modal function handle."""

    def __init__(self, *, app_name: str = APP_NAME) -> None:
        """Initialize the backend with the Modal app name."""
        self._app_name = app_name
        self._modal_function = lookup_run_ipython_cell(app_name)

    def run_cell(
        self,
        code_str: str,
        *,
        use_subprocess: bool = False,
        timeout_s: float | None = None,
        allow_mime: Iterable[str] | None = None,
        matplotlib_backend: str | None = ExecutionConfig.matplotlib_backend,
    ) -> dict[str, Any]:
        """Execute a code cell remotely using the Modal function."""
        allow_mime_csv = ",".join(allow_mime) if allow_mime else None
        return self._modal_function.remote(
            code_str,
            use_subprocess=use_subprocess,
            timeout_s=timeout_s,
            allow_mime=allow_mime_csv,
            matplotlib_backend=matplotlib_backend,
        )


def _run_ipython_cell_impl(
    code_str: str,
    *,
    use_subprocess: bool = False,
    timeout_s: float | None = None,
    allow_mime: str | None = None,
    matplotlib_backend: str | None = ExecutionConfig.matplotlib_backend,
) -> dict[str, Any]:
    """Execute code in an IPython shell and return normalized outputs."""
    allow_mime_values = _parse_allow_mime(allow_mime)
    session = IPythonSession(
        use_subprocess=use_subprocess,
        timeout_s=timeout_s,
        allow_mime=allow_mime_values,
        matplotlib_backend=matplotlib_backend,
    )
    return session.run_cell(code_str)


@app.function(
    image=image,
    restrict_modal_access=True,
    timeout=600,
    block_network=False,
)
def run_ipython_cell(
    code_str: str,
    *,
    use_subprocess: bool = False,
    timeout_s: float | None = None,
    allow_mime: str | None = None,
    matplotlib_backend: str | None = ExecutionConfig.matplotlib_backend,
) -> dict[str, Any]:
    """Execute code in an IPython shell and return normalized outputs.

    This wrapper is intentionally stateless to align with Modal Function
    execution, while still reusing the IPythonSession implementation.

    Args:
        code_str: The code cell to execute.
        use_subprocess: Whether to run the cell in a subprocess.
        timeout_s: Hard timeout in seconds; requires subprocess execution.
        allow_mime: Comma-separated MIME types to retain, e.g. "text/plain,image/png".
        matplotlib_backend: Matplotlib backend string for inline rendering.

    Returns:
        A dictionary with stdout, stderr, rich outputs, success, and error details.
    """
    return _run_ipython_cell_impl(
        code_str,
        use_subprocess=use_subprocess,
        timeout_s=timeout_s,
        allow_mime=allow_mime,
        matplotlib_backend=matplotlib_backend,
    )


def lookup_run_ipython_cell(app_name: str = APP_NAME) -> modal.Function:
    """Return the deployed Modal function handle for run_ipython_cell.

    Args:
        app_name: The Modal app name used at deployment time.

    Returns:
        A Modal Function handle for invoking run_ipython_cell remotely.
    """
    return modal.Function.from_name(app_name, RUN_IPYTHON_CELL_FUNCTION_NAME)


@app.local_entrypoint()
def main(
    code_str: str,
    *,
    use_subprocess: bool = False,
    timeout_s: float | None = None,
    allow_mime: str | None = None,
    matplotlib_backend: str | None = ExecutionConfig.matplotlib_backend,
) -> dict[str, Any]:
    """Run a single IPython cell via Modal and return its outputs.

    Args:
        code_str: The code cell to execute.
        use_subprocess: Whether to run the cell in a subprocess.
        timeout_s: Hard timeout in seconds; requires subprocess execution.
        allow_mime: Comma-separated MIME types to retain, e.g. "text/plain,image/png".
        matplotlib_backend: Matplotlib backend string for inline rendering.

    Returns:
        A dictionary with stdout, stderr, rich outputs, success, and error details.
    """
    return run_ipython_cell.remote(
        code_str,
        use_subprocess=use_subprocess,
        timeout_s=timeout_s,
        allow_mime=allow_mime,
        matplotlib_backend=matplotlib_backend,
    )
