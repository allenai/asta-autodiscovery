"""Local worker entry point that runs AutoDiscovery and emits its HTML report."""

from __future__ import annotations

import json
import shutil
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

from .args import ArgParser
from .copilot_provider import close_copilot_runtime
from .report import generate_report
from .run import main as run_main


def validate_run_completion(out_dir: str, requested_experiments: int) -> None:
    """Require the requested number of successful non-loading experiments."""
    nodes_path = Path(out_dir) / "mcts_nodes.json"
    if not nodes_path.is_file():
        raise RuntimeError("AutoDiscovery did not produce aggregate node results.")
    with nodes_path.open(encoding="utf-8") as nodes_file:
        nodes = json.load(nodes_file)
    if not isinstance(nodes, list):
        raise RuntimeError("AutoDiscovery aggregate node results are invalid.")
    successful = [
        node
        for node in nodes
        if isinstance(node, dict) and node.get("hypothesis") and node.get("success") is True
    ]
    if len(successful) < requested_experiments:
        raise RuntimeError(
            "AutoDiscovery completed "
            f"{len(successful)} of {requested_experiments} requested successful experiments. "
            "Partial artifacts and the report were preserved."
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the existing engine, generate its report, and clean its work directory."""
    args = ArgParser().parse_args(argv)
    try:
        run_main(args)
        generate_report(args.out_dir)
        validate_run_completion(args.out_dir, args.n_experiments)
        if args.delete_work_dir:
            shutil.rmtree(args.work_dir, ignore_errors=True)
    finally:
        with suppress(Exception):
            close_copilot_runtime()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
