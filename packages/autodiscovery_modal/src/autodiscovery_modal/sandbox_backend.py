"""Sandbox-based IPython execution backend for Modal."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any, Literal

import modal
from code_execution.ipython_session import ExecutionConfig

from .ipython_session import image

_DEFAULT_SANDBOX_TIMEOUT_S = 600
_SANDBOX_RUNNER = """
import json
import sys
import traceback

from code_execution.ipython_session import ExecutionConfig, IPythonSession


def _format_error(exc: BaseException) -> dict[str, str]:
    return {
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    }


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        allow_mime = payload.get("allow_mime")
        session = IPythonSession(
            use_subprocess=payload.get("use_subprocess", False),
            timeout_s=payload.get("timeout_s"),
            allow_mime=allow_mime,
            matplotlib_backend=payload.get("matplotlib_backend", ExecutionConfig.matplotlib_backend),
        )
        result = session.run_cell(payload["code_str"])
    except BaseException as exc:
        result = {
            "stdout": "",
            "stderr": "",
            "rich_outputs": [],
            "success": False,
            "error": _format_error(exc),
        }
    json.dump(result, sys.stdout)


if __name__ == "__main__":
    main()
"""


def _normalize_key_prefix(prefix: str) -> str:
    """Ensure CloudBucketMount key prefixes end with a trailing slash."""
    return prefix if prefix.endswith("/") else f"{prefix}/"


def _build_bucket_mount(
    *,
    bucket: str,
    key_prefix: str,
    read_only: bool,
    bucket_secret: modal.Secret | None,
    oidc_auth_role_arn: str | None,
) -> modal.CloudBucketMount:
    """Create a CloudBucketMount with consistent auth handling."""
    normalized_prefix = _normalize_key_prefix(key_prefix)
    mount_kwargs: dict[str, Any] = {
        "bucket_name": bucket,
        "key_prefix": normalized_prefix,
        "read_only": read_only,
    }
    if bucket_secret is not None:
        mount_kwargs["secret"] = bucket_secret
    if oidc_auth_role_arn is not None:
        mount_kwargs["oidc_auth_role_arn"] = oidc_auth_role_arn
    return modal.CloudBucketMount(**mount_kwargs)


def _coerce_stream_output(output: Any) -> str:
    """Normalize stream data to text for JSON parsing and error reporting."""
    if output is None:
        return ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return str(output)


class ModalSandboxIPythonBackend:
    """Backend that executes IPython cells inside a Modal Sandbox."""

    def __init__(
        self,
        *,
        app_name: str,
        bucket_mount: modal.CloudBucketMount,
        mount_path: str = "/data",
        env: dict[str, str] | None = None,
        sandbox_timeout_s: int = _DEFAULT_SANDBOX_TIMEOUT_S,
    ) -> None:
        """Initialize the backend with a Sandbox mount and environment settings.

        Args:
            app_name: Modal app name used to create Sandboxes.
            bucket_mount: CloudBucketMount scoped to the dataset prefix.
            mount_path: Path in the Sandbox where the dataset mount is attached.
            env: Environment variables for the Sandbox process.
            sandbox_timeout_s: Max Sandbox lifetime in seconds.
        """
        self._app = modal.App.lookup(app_name, create_if_missing=True)
        self._bucket_mount = bucket_mount
        self._mount_path = mount_path
        self._env = env or {}
        self._sandbox_timeout_s = sandbox_timeout_s

    @classmethod
    def for_run_dataset(
        cls,
        *,
        app_name: str,
        user_id: str,
        run_id: str,
        bucket: str,
        key_prefix: str,
        mount_path: str = "/data",
        auth_mode: Literal["per_user_role", "shared_role"] = "per_user_role",
        read_only: bool = True,
        bucket_secret: modal.Secret | None = None,
        oidc_auth_role_arn: str | None = None,
        env: dict[str, str] | None = None,
        sandbox_timeout_s: int = _DEFAULT_SANDBOX_TIMEOUT_S,
    ) -> "ModalSandboxIPythonBackend":
        """Create a Sandbox backend for a specific user/run dataset prefix.

        Args:
            app_name: Modal app name used to create Sandboxes.
            user_id: User identifier for labeling and environment metadata.
            run_id: Run identifier for labeling and environment metadata.
            bucket: Cloud bucket name backing the dataset.
            key_prefix: Prefix within the bucket to mount (must be a directory).
            mount_path: Path in the Sandbox where the dataset mount is attached.
            auth_mode: Indicates whether per-user or shared credentials are used.
                This backend does not enforce the policy; callers must pass the right credentials.
            read_only: Whether the mount should be read-only by default.
            bucket_secret: Modal Secret with bucket credentials, if needed.
            oidc_auth_role_arn: IAM role ARN for OIDC-based auth, if used.
            env: Environment variables for the Sandbox process.
            sandbox_timeout_s: Max Sandbox lifetime in seconds.

        Returns:
            A ModalSandboxIPythonBackend instance scoped to the run dataset.
        """
        _ = auth_mode
        bucket_mount = _build_bucket_mount(
            bucket=bucket,
            key_prefix=key_prefix,
            read_only=read_only,
            bucket_secret=bucket_secret,
            oidc_auth_role_arn=oidc_auth_role_arn,
        )
        runtime_env = {
            "USER_ID": user_id,
            "RUN_ID": run_id,
            "DATASET_ROOT": mount_path,
        }
        if env:
            runtime_env.update(env)
        return cls(
            app_name=app_name,
            bucket_mount=bucket_mount,
            mount_path=mount_path,
            env=runtime_env,
            sandbox_timeout_s=sandbox_timeout_s,
        )

    def run_cell(
        self,
        code_str: str,
        *,
        use_subprocess: bool = False,
        timeout_s: float | None = None,
        allow_mime: Iterable[str] | None = None,
        matplotlib_backend: str | None = ExecutionConfig.matplotlib_backend,
    ) -> dict[str, Any]:
        """Execute a code cell inside a fresh Sandbox and return normalized outputs."""
        secret = modal.Secret.from_dict(self._env) if self._env else None
        secrets = [secret] if secret is not None else []
        sandbox = modal.Sandbox.create(
            app=self._app,
            image=image,
            volumes={self._mount_path: self._bucket_mount},
            secrets=secrets,
            timeout=self._sandbox_timeout_s,
        )
        try:
            payload = {
                "code_str": code_str,
                "use_subprocess": use_subprocess,
                "timeout_s": timeout_s,
                "allow_mime": list(allow_mime) if allow_mime else None,
                "matplotlib_backend": matplotlib_backend,
            }
            process = sandbox.exec(
                "python",
                "-c",
                _SANDBOX_RUNNER,
                timeout=timeout_s,
            )
            process.stdin.write(json.dumps(payload).encode("utf-8"))
            process.stdin.write_eof()
            process.stdin.drain()
            process.wait()
            stdout = _coerce_stream_output(process.stdout.read())
            stderr = _coerce_stream_output(process.stderr.read())
        finally:
            sandbox.terminate()

        try:
            result = json.loads(stdout) if stdout else {}
        except json.JSONDecodeError:
            return {
                "stdout": "",
                "stderr": stderr or "",
                "rich_outputs": [],
                "success": False,
                "error": {
                    "type": "RuntimeError",
                    "message": "Sandbox output was not valid JSON.",
                    "traceback": stdout or "",
                },
            }

        if stderr:
            result.setdefault("stderr", "")
            result["stderr"] = f"{result['stderr']}{stderr}"
        return result
