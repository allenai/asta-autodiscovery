#!/usr/bin/env python3
"""Print a JSON args config as run.py CLI flags, one per line.

Booleans become --key / --no-key (every bool arg is a BooleanOptionalAction);
null values are skipped (leaving argparse's default). Keys listed after the
config path are skipped (e.g. ones the caller overrides).

Usage: _config_to_flags.py <config.json> [skip_key ...]
"""
import json
import sys

cfg = json.load(open(sys.argv[1]))
skip = set(sys.argv[2:])
for k, v in cfg.items():
    if k in skip or v is None:
        continue
    if isinstance(v, bool):
        print(f"--{k}" if v else f"--no-{k}")
    else:
        print(f"--{k}={v}")
