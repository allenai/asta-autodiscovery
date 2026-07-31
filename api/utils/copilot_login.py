"""Managed Copilot OAuth login process for the local application."""

from __future__ import annotations

import os
import re
import subprocess
import threading
from pathlib import Path
from typing import Any

_ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
_DEVICE_CODE = re.compile(r"\b[A-Z0-9]{4}-[A-Z0-9]{4}\b", re.IGNORECASE)
_URL = re.compile(r"https://[^\s]+")
_MAX_OUTPUT_CHARS = 8_000

_lock = threading.Lock()
_process: subprocess.Popen[str] | None = None
_output_path: Path | None = None


def start(executable: str, local_root: str) -> dict[str, Any]:
    """Start a fresh official login flow and capture its user-facing output."""
    global _process, _output_path
    with _lock:
        if _process is not None and _process.poll() is None:
            _process.terminate()
        state_dir = Path(local_root).expanduser().resolve() / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        _output_path = state_dir / "copilot-login.log"
        output = _output_path.open("w", encoding="utf-8")
        try:
            environment = os.environ.copy()
            environment["COPILOT_HOME"] = os.environ.get(
                "AUTODISCOVERY_COPILOT_HOME",
                str(Path.home() / ".copilot" / "autodiscovery"),
            )
            _process = subprocess.Popen(
                [executable, "--no-color", "login"],
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                start_new_session=True,
            )
        finally:
            output.close()
    return status()


def status() -> dict[str, Any]:
    """Return bounded, parsed login output suitable for the local renderer."""
    with _lock:
        process = _process
        output_path = _output_path
    output = ""
    if output_path and output_path.is_file():
        output = _ANSI_ESCAPE.sub("", output_path.read_text(encoding="utf-8", errors="replace"))
        output = output[-_MAX_OUTPUT_CHARS:]
    code_match = _DEVICE_CODE.search(output)
    url_match = _URL.search(output)
    return_code = process.poll() if process is not None else None
    if process is None:
        phase = "idle"
    elif return_code is None:
        phase = "running"
    elif return_code == 0:
        phase = "completed"
    else:
        phase = "failed"
    return {
        "phase": phase,
        "device_code": code_match.group(0).upper() if code_match else None,
        "verification_url": url_match.group(0).rstrip(".,)") if url_match else None,
        "output": output,
        "return_code": return_code,
    }
