"""Stateless IPython execution helpers for use in Modal functions."""

from typing import Any

import modal

from code_execution.ipython_session import ExecutionConfig, IPythonSession

app = modal.App("autodiscovery")
image = (
    modal.Image.debian_slim()
    .uv_pip_install("ipython>=9.8.0")
    .add_local_python_source("code_execution")
)

@app.function(
    image=image,
    restrict_modal_access=True,
    max_inputs=1,
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
    allow_mime_values = [item.strip() for item in allow_mime.split(",") if item.strip()] if allow_mime else None
    session = IPythonSession(
        use_subprocess=use_subprocess,
        timeout_s=timeout_s,
        allow_mime=allow_mime_values,
        matplotlib_backend=matplotlib_backend,
    )
    return session.run_cell(code_str)
