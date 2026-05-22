#!/usr/bin/env python3
"""Version management for asta-autodiscovery.

Keeps version in sync across all workspace pyproject.toml files and the
autodiscovery_jobs __init__.py. The autodiscovery package's pyproject.toml
is the source of truth.
"""

import re
import sys
from pathlib import Path

RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
NC = "\033[0m"

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

SOURCE_OF_TRUTH = PROJECT_ROOT / "packages" / "autodiscovery" / "pyproject.toml"

PYPROJECT_FILES = [
    PROJECT_ROOT / "pyproject.toml",
    PROJECT_ROOT / "packages" / "autodiscovery" / "pyproject.toml",
    PROJECT_ROOT / "packages" / "agents" / "pyproject.toml",
    PROJECT_ROOT / "packages" / "code_execution" / "pyproject.toml",
    PROJECT_ROOT / "packages" / "autodiscovery_modal" / "pyproject.toml",
    PROJECT_ROOT / "packages" / "autodiscovery_jobs" / "pyproject.toml",
    PROJECT_ROOT / "packages" / "devtools" / "pyproject.toml",
]

INIT_FILES = [
    PROJECT_ROOT / "packages" / "autodiscovery_jobs" / "src" / "autodiscovery_jobs" / "__init__.py",
]


def read_pyproject_version(path: Path) -> str:
    match = re.search(r'^version = "([^"]+)"', path.read_text(), re.MULTILINE)
    if not match:
        raise ValueError(f"Could not find version in {path}")
    return match.group(1)


def read_init_version(path: Path) -> str:
    match = re.search(r'__version__ = "([^"]+)"', path.read_text())
    if not match:
        raise ValueError(f"Could not find __version__ in {path}")
    return match.group(1)


def write_pyproject_version(path: Path, version: str) -> None:
    content = path.read_text()
    content = re.sub(
        r'^version = "[^"]+"', f'version = "{version}"', content, count=1, flags=re.MULTILINE
    )
    path.write_text(content)


def write_init_version(path: Path, version: str) -> None:
    content = path.read_text()
    content = re.sub(r'__version__ = "[^"]+"', f'__version__ = "{version}"', content)
    path.write_text(content)


def check_version_consistency() -> bool:
    source_version = read_pyproject_version(SOURCE_OF_TRUTH)
    mismatches: list[tuple[Path, str]] = []

    for path in PYPROJECT_FILES:
        v = read_pyproject_version(path)
        if v != source_version:
            mismatches.append((path, v))

    for path in INIT_FILES:
        v = read_init_version(path)
        if v != source_version:
            mismatches.append((path, v))

    if mismatches:
        print(f"{RED}Error: Version mismatch detected:{NC}")
        print(f"  source of truth ({SOURCE_OF_TRUTH.relative_to(PROJECT_ROOT)}): {source_version}")
        for path, v in mismatches:
            print(f"  {path.relative_to(PROJECT_ROOT)}: {v}")
        print()
        print("Run 'make set-version VERSION=x.y.z' to sync versions")
        return False

    print(f"{GREEN}✓ All version files are consistent: {source_version}{NC}")
    return True


def validate_version_format(version: str) -> bool:
    return bool(re.match(r"^\d+\.\d+\.\d+$", version))


def set_version(new_version: str) -> bool:
    if not validate_version_format(new_version):
        print(f"{RED}Error: Version must be in format x.y.z (e.g., 1.2.3){NC}")
        return False

    print(f"Setting version to {new_version} in all files...")

    for path in PYPROJECT_FILES:
        print(f"  Updating {path.relative_to(PROJECT_ROOT)}")
        write_pyproject_version(path, new_version)

    for path in INIT_FILES:
        print(f"  Updating {path.relative_to(PROJECT_ROOT)}")
        write_init_version(path, new_version)

    print(f"{GREEN}✓ Version updated to {new_version}{NC}")
    print()
    print(f"{YELLOW}Next steps:{NC}")
    print("  1. Review changes: git diff")
    print(f"  2. Commit changes: git add -A && git commit -m 'chore: bump version to {new_version}'")
    print("  3. Push tag: make push-version-tag")
    return True


def show_version() -> None:
    print(read_pyproject_version(SOURCE_OF_TRUTH))


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: manage-version.py {check|set VERSION|show}")
        print()
        print("Commands:")
        print("  check      Check version consistency across all files")
        print("  set        Set version in all files (requires VERSION argument)")
        print("  show       Show current version")
        return 1

    command = sys.argv[1]

    if command == "check":
        return 0 if check_version_consistency() else 1
    elif command == "set":
        if len(sys.argv) < 3:
            print(f"{RED}Error: VERSION parameter is required{NC}")
            print("Usage: manage-version.py set VERSION")
            return 1
        return 0 if set_version(sys.argv[2]) else 1
    elif command == "show":
        show_version()
        return 0
    else:
        print(f"{RED}Error: Unknown command '{command}'{NC}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
