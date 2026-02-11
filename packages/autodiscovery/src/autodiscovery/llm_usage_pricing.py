"""Post-processing utilities for applying pricing to token-usage events."""

from __future__ import annotations

import argparse
import json
import logging
import os

from autodiscovery.llm_usage import (
    build_priced_summary,
    load_pricing_catalog,
    load_usage_events,
    price_usage_events,
    save_usage_events,
)

logger = logging.getLogger(__name__)


def _default_out_path(events_path: str, suffix: str) -> str:
    """Build an output path next to the events file.

    Args:
        events_path: Input events path.
        suffix: Filename suffix to append.

    Returns:
        Derived output path.
    """
    directory = os.path.dirname(events_path) or "."
    return os.path.join(directory, suffix)


def main() -> None:
    """Apply pricing to a token-usage events file and persist priced artifacts."""
    parser = argparse.ArgumentParser(description="Apply pricing to llm_usage_events.jsonl.")
    parser.add_argument(
        "--events_file",
        type=str,
        required=True,
        help="Path to token-usage events JSONL file.",
    )
    parser.add_argument(
        "--pricing_file",
        type=str,
        required=True,
        help="Path to pricing JSON file.",
    )
    parser.add_argument(
        "--out_events_file",
        type=str,
        help="Optional output path for priced events JSONL.",
    )
    parser.add_argument(
        "--out_summary_file",
        type=str,
        help="Optional output path for priced summary JSON.",
    )
    args = parser.parse_args()

    events = load_usage_events(args.events_file)
    pricing_catalog = load_pricing_catalog(args.pricing_file)
    priced_events = price_usage_events(events, pricing_catalog)
    priced_summary = build_priced_summary(priced_events)

    out_events_file = args.out_events_file or _default_out_path(
        args.events_file, "llm_usage_priced_events.jsonl"
    )
    out_summary_file = args.out_summary_file or _default_out_path(
        args.events_file, "llm_usage_priced_summary.json"
    )

    save_usage_events(priced_events, out_events_file)
    with open(out_summary_file, "w") as f:
        json.dump(priced_summary, f, indent=2)

    logger.info("[pricing] Priced events saved to %s", out_events_file)
    logger.info("[pricing] Priced summary saved to %s", out_summary_file)


if __name__ == "__main__":
    main()
