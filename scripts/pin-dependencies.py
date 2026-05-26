#!/usr/bin/env python3
"""Pin a workspace package's dependencies from uv.lock for publishing.

Rewrites packages/<name>/pyproject.toml so the `dependencies` list contains
the full pinned closure resolved by uv (transitive + direct + workspace
siblings). Run this in CI before `uv build --package <name>` so the published
wheel reproduces the locked environment under `uv tool install` / `pip install`.

This is destructive — only run on a fresh checkout in CI; do not commit.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = PROJECT_ROOT / "packages"


def workspace_package_versions() -> dict[str, tuple[str, Path]]:
    """Map workspace project name → (version, directory)."""
    name_re = re.compile(r'^name\s*=\s*"([^"]+)"', re.MULTILINE)
    version_re = re.compile(r'^version\s*=\s*"([^"]+)"', re.MULTILINE)
    out: dict[str, tuple[str, Path]] = {}
    for pyproject in PACKAGES_DIR.glob("*/pyproject.toml"):
        text = pyproject.read_text()
        name_m = name_re.search(text)
        version_m = version_re.search(text)
        if not name_m or not version_m:
            raise RuntimeError(f"Missing name/version in {pyproject}")
        out[name_m.group(1)] = (version_m.group(1), pyproject.parent)
    return out


def find_pyproject(package: str, members: dict[str, tuple[str, Path]]) -> Path:
    if package not in members:
        raise SystemExit(f"No workspace package named {package!r}")
    return members[package][1] / "pyproject.toml"


def export_closure(package: str) -> list[str]:
    """Return resolved requirement lines for the given workspace package.

    Workspace siblings appear as `-e ./packages/<dir>` editable references and
    are translated to `<name>==<version>` pins from the sibling's pyproject.
    """
    result = subprocess.run(
        [
            "uv",
            "export",
            "--package",
            package,
            "--no-emit-project",
            "--no-dev",
            "--no-hashes",
            "--no-annotate",
            "--no-header",
            "--frozen",
            "--format",
            "requirements-txt",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
    )

    members = workspace_package_versions()
    dir_to_name_version = {dir_: (name, version) for name, (version, dir_) in members.items()}

    pins: list[str] = []
    for raw in result.stdout.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("-e "):
            target = (PROJECT_ROOT / line[3:].strip()).resolve()
            if target not in dir_to_name_version:
                raise RuntimeError(f"Unknown editable target in export: {line!r}")
            sib_name, sib_version = dir_to_name_version[target]
            pins.append(f"{sib_name}=={sib_version}")
        else:
            pins.append(line)
    return pins


def rewrite_dependencies(pyproject_path: Path, pins: list[str]) -> None:
    text = pyproject_path.read_text()

    body = "\n".join(f'    "{pin}",' for pin in pins)
    replacement = f"dependencies = [\n{body}\n]"

    # Match `dependencies = [ ... ]` where the closing `]` sits at column 0,
    # so we don't terminate prematurely on `]` inside a quoted requirement
    # like `ag2[openai, gemini]==0.10`.
    pattern = re.compile(r"^dependencies\s*=\s*\[.*?^\]", re.DOTALL | re.MULTILINE)
    new_text, n = pattern.subn(replacement, text, count=1)
    if n != 1:
        raise RuntimeError(
            f"Could not locate dependencies block in {pyproject_path} "
            "(expected closing `]` at column 0)"
        )

    pyproject_path.write_text(new_text)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: pin-dependencies.py PACKAGE_NAME", file=sys.stderr)
        return 1

    package = sys.argv[1]
    members = workspace_package_versions()
    pyproject = find_pyproject(package, members)
    pins = export_closure(package)
    rewrite_dependencies(pyproject, pins)
    print(f"Pinned {len(pins)} dependencies in {pyproject.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
