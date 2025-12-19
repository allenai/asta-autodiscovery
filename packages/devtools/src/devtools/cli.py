"""Command-line interface for running code through IPythonSession."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable

from code_execution.ipython_session import ExecutionConfig, IPythonSession


def _parse_allow_mime(values: Iterable[str] | None) -> set[str] | None:
    if not values:
        return None
    allow_mime: set[str] = set()
    for item in values:
        allow_mime.update(part.strip() for part in item.split(",") if part.strip())
    return allow_mime or None


def _read_code(args: argparse.Namespace) -> str:
    if args.code and args.file:
        raise ValueError("Use only one of --code or --file")
    if args.code:
        return args.code
    if args.file:
        contents = args.file.read()
        args.file.close()
        return contents
    if sys.stdin.isatty():
        raise ValueError("No code supplied; use --code, --file, or stdin")
    return sys.stdin.read()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run code through IPythonSession and emit JSON results.",
    )
    parser.add_argument(
        "-c",
        "--code",
        help="Code snippet to execute.",
    )
    parser.add_argument(
        "-f",
        "--file",
        type=argparse.FileType("r", encoding="utf-8"),
        help="Read code from a file.",
    )
    parser.add_argument(
        "--use-subprocess",
        action="store_true",
        help="Execute in a subprocess to enable hard timeouts.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help="Timeout in seconds (requires --use-subprocess).",
    )
    parser.add_argument(
        "--allow-mime",
        action="append",
        help="Comma-separated MIME allowlist entries (repeatable).",
    )
    parser.add_argument(
        "--matplotlib-backend",
        default=ExecutionConfig.matplotlib_backend,
        help="Matplotlib backend string to use (default matches IPythonSession).",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a code snippet via IPythonSession and print the JSON result."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        code_str = _read_code(args)
    except ValueError as exc:
        parser.error(str(exc))
        return 2

    allow_mime = _parse_allow_mime(args.allow_mime)

    session = IPythonSession(
        use_subprocess=args.use_subprocess,
        timeout_s=args.timeout,
        allow_mime=allow_mime,
        matplotlib_backend=args.matplotlib_backend,
    )
    results = session.run_cell(code_str)

    json.dump(
        results,
        sys.stdout,
        ensure_ascii=True,
        indent=2 if args.pretty else None,
        sort_keys=args.pretty,
    )
    sys.stdout.write("\n")
    return 0 if results.get("success") else 1


if __name__ == "__main__":
    raise SystemExit(main())
