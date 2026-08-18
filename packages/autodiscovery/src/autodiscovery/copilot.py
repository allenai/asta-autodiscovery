"""Credential-safe diagnostics for the optional GitHub Copilot provider."""

from __future__ import annotations

import argparse
import contextlib
import importlib.metadata
import json
import os
import re
import shutil
import subprocess
from typing import Any


def _runtime_info() -> dict[str, str | None]:
    configured_path = os.getenv("COPILOT_CLI_PATH")
    executable = configured_path or shutil.which("copilot")
    source = "configured" if executable else "downloaded"
    version = None
    if executable:
        try:
            result = subprocess.run(
                [executable, "--version"],
                capture_output=True,
                check=False,
                text=True,
                timeout=10,
            )
            output = (result.stdout or "").strip()
            match = re.search(r"\b\d+\.\d+\.\d+\b", output)
            version = match.group(0) if match else None
        except (OSError, subprocess.SubprocessError):
            pass
    return {"version": version, "source": source}


def _safe_model(model: Any) -> dict[str, Any]:
    capabilities = getattr(model, "capabilities", None)
    supports = getattr(capabilities, "supports", None)
    billing = getattr(model, "billing", None)
    token_prices = getattr(billing, "token_prices", None)
    input_price = getattr(token_prices, "input_price", None)
    output_price = getattr(token_prices, "output_price", None)
    safe = {
        "id": getattr(model, "id", None),
        "name": getattr(model, "name", None),
        "vision": bool(getattr(supports, "vision", False)),
        "reasoning_efforts": list(getattr(model, "supported_reasoning_efforts", None) or []),
    }
    if isinstance(input_price, (int, float)) and isinstance(output_price, (int, float)):
        safe["pricing"] = {
            "input_per_million_usd": input_price * 0.01,
            "output_per_million_usd": output_price * 0.01,
        }
    return safe


def _classify_error(exc: Exception) -> tuple[str, str]:
    text = str(exc).lower()
    if isinstance(exc, ImportError):
        return "SDK_MISSING", "Install the Copilot extra: pip install 'asta-autodiscovery[copilot]'"
    if "seat" in text or "entitlement" in text:
        return "SEAT_REQUIRED", "Confirm that the GitHub account has an active Copilot seat."
    if "policy" in text or "blocked" in text or "forbidden" in text:
        return "POLICY_BLOCKED", "Ask the Copilot administrator to allow the requested models."
    if "not authenticated" in text or "login" in text or "auth" in text:
        return "AUTH_REQUIRED", "Run 'copilot login', then retry the diagnostic."
    if "download" in text or "certificate" in text or "ssl" in text:
        return "RUNTIME_DOWNLOAD_FAILED", "Set COPILOT_CLI_PATH to an installed Copilot CLI."
    if "model" in text and ("unavailable" in text or "unsupported" in text):
        return "MODEL_UNAVAILABLE", "Choose a model listed by this diagnostic."
    if "runtime" in text or "executable" in text or "enoent" in text:
        return "RUNTIME_MISSING", "Install the Copilot CLI or allow the SDK runtime download."
    return "REQUEST_FAILED", "Retry the diagnostic and inspect local Copilot runtime logs."


def doctor() -> dict[str, Any]:
    """Check the SDK, authenticated runtime, and available model catalog."""
    result: dict[str, Any] = {
        "provider": "copilot",
        "status": "error",
        "code": "REQUEST_FAILED",
        "message": "Copilot diagnostic did not complete.",
        "remediation": None,
        "sdk": {"version": None},
        "runtime": _runtime_info(),
        "account": {"authenticated": False, "label": None},
        "models": [],
    }
    try:
        result["sdk"]["version"] = importlib.metadata.version("github-copilot-sdk")
        from autodiscovery.copilot_provider import CopilotRuntime

        runtime = CopilotRuntime()
        try:
            models = runtime.list_models()
        finally:
            with contextlib.suppress(Exception):
                runtime.close()
        result.update(
            status="ready",
            code="READY",
            message=f"Copilot is authenticated and exposes {len(models)} model(s).",
            account={"authenticated": True, "label": None},
            models=[_safe_model(model) for model in models],
        )
    except Exception as exc:
        code, remediation = _classify_error(exc)
        result.update(
            code=code,
            message=f"Copilot diagnostic failed: {exc.__class__.__name__}.",
            remediation=remediation,
        )
    return result


def main(argv: list[str] | None = None) -> int:
    """Run Copilot diagnostics from the command line."""
    parser = argparse.ArgumentParser(description="GitHub Copilot provider diagnostics")
    subparsers = parser.add_subparsers(dest="command", required=True)
    doctor_parser = subparsers.add_parser("doctor", help="Check SDK, auth, and model access")
    doctor_parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    diagnostic = doctor()
    if args.as_json:
        print(json.dumps(diagnostic, indent=2))  # noqa: T201 - CLI output
    else:
        print(f"{diagnostic['status']}: {diagnostic['message']}")  # noqa: T201 - CLI output
        if diagnostic["remediation"]:
            print(diagnostic["remediation"])  # noqa: T201 - CLI output
    return 0 if diagnostic["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
