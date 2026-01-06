"""IPython-backed execution helpers with optional subprocess isolation."""

import base64
import traceback
from collections.abc import Iterable
from dataclasses import dataclass
from multiprocessing import get_context
from typing import Any, cast

from IPython.core.formatters import DisplayFormatter
from IPython.core.interactiveshell import InteractiveShell
from IPython.utils.capture import capture_output


@dataclass(frozen=True)
class ExecutionConfig:
    """Configuration for controlling how an IPython session executes cells."""

    use_subprocess: bool = False
    timeout_s: float | None = None
    allow_mime: frozenset[str] = frozenset(
        {
            "text/plain",
            "text/html",
            "text/markdown",
            "text/latex",
            "image/png",
            "image/svg+xml",
            "image/jpeg",
            "application/json",
            "application/javascript",
            "application/pdf",
        }
    )
    matplotlib_backend: str | None = "module://matplotlib_inline.backend_inline"


def _normalize_value(value: Any) -> Any:
    # Ensure outputs are JSON-safe for downstream serialization.
    if isinstance(value, bytes):
        return base64.b64encode(value).decode("ascii")
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_value(item) for key, item in value.items()}
    return repr(value)


def _normalize_mime_bundle(data: dict[str, Any], allow_mime: frozenset[str]) -> dict[str, Any]:
    # Filter to a predictable MIME allowlist to avoid leaking unexpected payload types.
    normalized: dict[str, Any] = {}
    for mime_type, payload in data.items():
        if mime_type not in allow_mime:
            continue
        normalized[mime_type] = _normalize_value(payload)
    return normalized


def _format_error(exc: BaseException | None) -> dict[str, str] | None:
    # Preserve traceback details so callers can render useful diagnostics.
    if exc is None:
        return None
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    }


def _run_cell_with_shell(
    shell: InteractiveShell,
    code_str: str,
    allow_mime: frozenset[str],
) -> dict[str, Any]:
    # Execute in-process to preserve state between calls when isolation isn't needed.
    with capture_output() as captured:
        result = shell.run_cell(code_str)

    error = result.error_before_exec or result.error_in_exec
    outputs = {
        "stdout": captured.stdout,
        "stderr": captured.stderr,
        "rich_outputs": [],
        "success": result.success,
        "error": _format_error(error),
    }

    for display_obj in captured.outputs:
        outputs["rich_outputs"].append(_normalize_mime_bundle(display_obj.data, allow_mime))

    return outputs


def _configure_display_formatters(
    shell: InteractiveShell,
    allow_mime: frozenset[str],
) -> None:
    formatter = shell.display_formatter
    if formatter is None:
        return
    display_formatter = cast(DisplayFormatter, formatter)
    available = [mime for mime in allow_mime if mime in display_formatter.formatters]
    if not available:
        return
    for mime in available:
        display_formatter.formatters[mime].enabled = True
    display_formatter.active_types = available


def _configure_matplotlib_backend(
    backend: str | None,
    allow_mime: frozenset[str],
) -> None:
    if not backend:
        return
    try:
        import matplotlib
        import matplotlib_inline.backend_inline as backend_inline
    except Exception:
        return

    try:
        current = matplotlib.get_backend()
    except Exception:
        current = None

    if current == backend:
        return

    try:
        # Ensure rich display payloads are emitted in non-interactive contexts.
        matplotlib.use(backend, force=True)
        if "matplotlib_inline.backend_inline" in backend:
            formats: list[str] = []
            if "image/png" in allow_mime:
                formats.append("png")
            if "image/svg+xml" in allow_mime:
                formats.append("svg")
            if "image/jpeg" in allow_mime:
                formats.append("jpeg")
            if formats:
                backend_inline.set_matplotlib_formats(*formats)
    except Exception:
        # If pyplot or another backend is already loaded, keep running.
        return


def _configure_shell(
    shell: InteractiveShell,
    allow_mime: frozenset[str],
    matplotlib_backend: str | None,
) -> None:
    _configure_display_formatters(shell, allow_mime)
    _configure_matplotlib_backend(matplotlib_backend, allow_mime)


def _ensure_pip_available() -> None:
    # Bootstrap pip so %pip magic can install packages on demand.
    try:
        import pip  # noqa: F401
        return
    except Exception:
        pass

    try:
        import ensurepip
    except Exception:
        return

    try:
        ensurepip.bootstrap()
    except Exception:
        return


def _run_cell_in_subprocess(
    code_str: str,
    allow_mime: frozenset[str],
    matplotlib_backend: str | None,
    connection,
) -> None:
    # Run in a child process so a hard timeout can be enforced without blocking.
    shell = InteractiveShell.instance()
    _configure_shell(shell, allow_mime, matplotlib_backend)
    outputs = _run_cell_with_shell(shell, code_str, allow_mime)
    connection.send(outputs)
    connection.close()


class IPythonSession:
    """Run code in an IPython shell with optional subprocess isolation."""

    def __init__(
        self,
        *,
        use_subprocess: bool = False,
        timeout_s: float | None = None,
        allow_mime: Iterable[str] | None = None,
        matplotlib_backend: str | None = ExecutionConfig.matplotlib_backend,
    ) -> None:
        """Initialize an IPython execution session with optional isolation settings."""
        _ensure_pip_available()
        self._config = ExecutionConfig(
            use_subprocess=use_subprocess,
            timeout_s=timeout_s,
            allow_mime=frozenset(allow_mime or ExecutionConfig.allow_mime),
            matplotlib_backend=matplotlib_backend,
        )
        # Create a shell instance that persists variables between calls.
        self.shell = InteractiveShell.instance()
        _configure_shell(self.shell, self._config.allow_mime, self._config.matplotlib_backend)

    def run_cell(self, code_str: str) -> dict[str, Any]:
        """Run a code cell and return captured outputs, errors, and success state."""
        if self._config.timeout_s is not None and not self._config.use_subprocess:
            raise ValueError("timeout_s requires use_subprocess=True to enforce a hard timeout")
        if not self._config.use_subprocess:
            return _run_cell_with_shell(self.shell, code_str, self._config.allow_mime)

        ctx = get_context("spawn")
        parent_conn, child_conn = ctx.Pipe(duplex=False)
        process = ctx.Process(
            target=_run_cell_in_subprocess,
            args=(code_str, self._config.allow_mime, self._config.matplotlib_backend, child_conn),
        )
        process.start()
        child_conn.close()
        process.join(timeout=self._config.timeout_s)

        if process.is_alive():
            process.terminate()
            process.join()
            parent_conn.close()
            return {
                "stdout": "",
                "stderr": "",
                "rich_outputs": [],
                "success": False,
                "error": {
                    "type": "TimeoutError",
                    "message": f"Execution exceeded {self._config.timeout_s} seconds",
                    "traceback": "",
                },
            }

        if parent_conn.poll():
            result = parent_conn.recv()
            parent_conn.close()
            return result

        parent_conn.close()

        return {
            "stdout": "",
            "stderr": "",
            "rich_outputs": [],
            "success": False,
            "error": {
                "type": "RuntimeError",
                "message": "Subprocess exited without returning a result",
                "traceback": "",
            },
        }
