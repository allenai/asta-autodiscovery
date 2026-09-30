"""Read-only data-library directories available to a run.

A data-library directory is a directory tree the run reads in place rather than
a dataset file listed in the metadata: it may hold one dataset or many, in any
layout, so the agents are given a *manifest* of it — its ``README.md`` plus a
bounded view of its file tree — and left to work out what to use.

The directories appear at the same path in every environment (the job container
and any code-execution sandbox), so the paths in the manifest are the paths the
generated code opens.
"""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import asdict, dataclass, field

#: File at the top of a directory that describes it.
README_NAME = "README.md"

# Bounds on how much of a directory is inspected and shown. Directories may be
# very large and are often a network mount, so the walk is capped by entries
# visited, not just by what is displayed.
_MAX_README_CHARS = 8000
_MAX_DEPTH = 3
_MAX_ENTRIES_PER_DIR = 15
_MAX_ENTRIES_VISITED = 5000


@dataclass
class DatalibManifest:
    """What the agents are told about one data-library directory."""

    path: str
    readme: str | None
    tree: list[str]
    n_files: int
    n_dirs: int
    total_bytes: int
    extensions: dict[str, int] = field(default_factory=dict)
    truncated: bool = False

    def to_dict(self) -> dict:
        """Return a JSON-serializable dict (for provenance in the run output)."""
        return asdict(self)


def build_manifest(path: str) -> DatalibManifest:
    """Inspect one data-library directory.

    Raises:
        FileNotFoundError: If ``path`` is not a directory.
    """
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Data library directory not found: {path}")

    readme = None
    readme_path = os.path.join(path, README_NAME)
    if os.path.isfile(readme_path):
        with open(readme_path, encoding="utf-8", errors="replace") as f:
            readme = f.read(_MAX_README_CHARS + 1)
        if len(readme) > _MAX_README_CHARS:
            readme = readme[:_MAX_README_CHARS] + "\n[... README truncated ...]"

    walk = _Walk()
    walk.visit(path, depth=0)
    return DatalibManifest(
        path=path,
        readme=readme,
        tree=walk.lines,
        n_files=walk.n_files,
        n_dirs=walk.n_dirs,
        total_bytes=walk.total_bytes,
        extensions=dict(walk.extensions.most_common()),
        truncated=walk.truncated,
    )


def build_manifests(paths: list[str]) -> list[DatalibManifest]:
    """Inspect each directory in ``paths``, in order."""
    return [build_manifest(p) for p in paths]


class _Walk:
    """Depth-first walk that renders a bounded, indented tree and tallies stats."""

    def __init__(self):
        self.lines: list[str] = []
        self.n_files = 0
        self.n_dirs = 0
        self.total_bytes = 0
        self.extensions: Counter[str] = Counter()
        self.visited = 0
        self.truncated = False

    def visit(self, dirpath: str, depth: int, display: bool = True) -> None:
        """Tally ``dirpath``'s entries, rendering them only while ``display``."""
        try:
            with os.scandir(dirpath) as it:
                entries = sorted(it, key=lambda e: (not _is_dir(e), e.name))
        except OSError:
            return

        indent = "  " * depth
        for i, entry in enumerate(entries):
            if self.visited >= _MAX_ENTRIES_VISITED:
                self.truncated = True
                return
            self.visited += 1
            shown = display and i < _MAX_ENTRIES_PER_DIR
            if _is_dir(entry):
                self.n_dirs += 1
                if shown:
                    self.lines.append(f"{indent}{entry.name}/")
                if depth + 1 < _MAX_DEPTH:
                    self.visit(entry.path, depth + 1, display=shown)
                else:
                    # Deeper levels are neither shown nor counted.
                    self.truncated = True
                    if shown:
                        self.lines.append(f"{indent}  ...")
            else:
                size = _size(entry)
                self.n_files += 1
                self.total_bytes += size
                self.extensions[os.path.splitext(entry.name)[1].lower() or "(none)"] += 1
                if shown:
                    self.lines.append(f"{indent}{entry.name} ({_human_size(size)})")

        if display and len(entries) > _MAX_ENTRIES_PER_DIR:
            self.lines.append(f"{indent}... and {len(entries) - _MAX_ENTRIES_PER_DIR} more")


def _is_dir(entry: os.DirEntry) -> bool:
    try:
        return entry.is_dir()
    except OSError:
        return False


def _size(entry: os.DirEntry) -> int:
    try:
        return entry.stat().st_size
    except OSError:
        return 0


def _human_size(n: int) -> str:
    size = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"  # unreachable


def describe(manifests: list[DatalibManifest]) -> str:
    """Render manifests as the prompt text describing the data library."""
    parts = ["##### DATA LIBRARY (READ-ONLY) #####"]
    for m in manifests:
        parts.append(f"\n### DIRECTORY: {m.path} ###")
        stats = (
            f"{m.n_files} files in {m.n_dirs} subdirectories, {_human_size(m.total_bytes)} total"
        )
        if m.truncated:
            stats += " (counted from a partial listing; there is more than this)"
        parts.append(stats)
        if m.extensions:
            top = ", ".join(f"{ext}: {n}" for ext, n in list(m.extensions.items())[:10])
            parts.append(f"File types: {top}")
        parts.append("\nREADME.md:" if m.readme else "\n(No README.md provided.)")
        if m.readme:
            parts.append(m.readme.strip())
        parts.append("\nLayout:")
        parts.extend(m.tree or ["(empty)"])
    return "\n".join(parts)


def prompt_note(paths: list[str]) -> str:
    """One-paragraph reminder, for agent system prompts, that the library exists.

    The full manifest is given once, in the first (data-loading) experiment; the
    agents only need to know here that these paths are part of the provided data.
    """
    if not paths:
        return ""
    listed = ", ".join(paths)
    return (
        "In addition to any dataset files, the provided data includes these read-only "
        f"data library directories, available at these absolute paths: {listed}. "
        "They are described (README and file layout) in the first, data-loading experiment. "
        "Treat their contents as provided data; never write to them. "
        "They may be very large: check file sizes and read selectively (specific files, "
        "chunks, sampled rows, or lazy/backed modes) rather than loading everything into memory. "
    )


def gs_source(path: str, store_root: str, store_uri: str) -> tuple[str, str]:
    """Map a store-shaped local path to the ``(bucket, key_prefix)`` it mirrors.

    ``store_root`` is where the store is mounted (e.g. ``/mnt/data``) and
    ``store_uri`` the ``gs://bucket`` it mirrors, so ``/mnt/data/users/u/datalib/x``
    maps to ``("bucket", "users/u/datalib/x/")``.

    Raises:
        ValueError: If ``path`` is not under ``store_root`` or ``store_uri`` is
            not a ``gs://`` URI.
    """
    if not store_uri.startswith("gs://"):
        raise ValueError(f"--store_uri must be a gs:// URI, got {store_uri!r}")
    root = os.path.normpath(store_root)
    norm = os.path.normpath(path)
    if os.path.commonpath([root, norm]) != root or norm == root:
        raise ValueError(f"Data library directory {path!r} is not under --store_root {root!r}")
    bucket, _, base = store_uri[len("gs://") :].partition("/")
    rel = os.path.relpath(norm, root)
    key_prefix = f"{base.strip('/')}/{rel}/" if base.strip("/") else f"{rel}/"
    return bucket, key_prefix
