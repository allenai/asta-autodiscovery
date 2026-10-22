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
from collections import Counter, deque
from dataclasses import asdict, dataclass, field

#: File at the top of a directory that describes it.
README_NAME = "README.md"

# Bounds on how much of a directory is inspected and shown. Directories may be
# very large and are often a network mount, so the walk is capped by entries
# visited, not just by what is displayed. The walk is breadth-first, so the cap
# cuts off the deepest levels first, and the rendered tree is capped separately
# so a wide directory cannot flood the prompt.
_MAX_README_CHARS = 8000
_MAX_DEPTH = 3
_MAX_ENTRIES_PER_DIR = 15
_MAX_ENTRIES_VISITED = 5000
_MAX_TREE_LINES = 200


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

    walk = _Walk(path)
    return DatalibManifest(
        path=path,
        readme=readme,
        tree=_bounded_tree(walk.root),
        n_files=walk.n_files,
        n_dirs=walk.n_dirs,
        total_bytes=walk.total_bytes,
        extensions=dict(walk.extensions.most_common()),
        truncated=walk.truncated,
    )


def build_manifests(paths: list[str]) -> list[DatalibManifest]:
    """Inspect each directory in ``paths``, in order."""
    return [build_manifest(p) for p in paths]


@dataclass
class _Dir:
    """A directory reached by the walk.

    ``entries`` holds ``(name, child)`` pairs in display order, where ``child`` is
    a :class:`_Dir` or a file size; it is ``None`` if the directory was never
    listed (too deep, or the walk ran out of budget). ``n_entries`` is the full
    size of the listing, which may be more than ``entries`` holds.
    """

    entries: list[tuple[str, _Dir | int]] | None = None
    n_entries: int = 0


class _Walk:
    """Breadth-first walk that records a bounded tree and tallies stats."""

    def __init__(self, path: str):
        self.n_files = 0
        self.n_dirs = 0
        self.total_bytes = 0
        self.extensions: Counter[str] = Counter()
        self.visited = 0
        self.truncated = False
        self.root = _Dir()

        queue = deque([(path, self.root, 0)])
        while queue:
            if self.visited >= _MAX_ENTRIES_VISITED:
                self.truncated = True
                return
            self._list(*queue.popleft(), queue)

    def _list(self, dirpath: str, node: _Dir, depth: int, queue: deque) -> None:
        """Tally ``dirpath``'s entries into ``node``, queueing its subdirectories."""
        node.entries = []
        try:
            with os.scandir(dirpath) as it:
                entries = sorted(it, key=lambda e: (not _is_dir(e), e.name))
        except OSError:
            return
        node.n_entries = len(entries)

        for entry in entries:
            if self.visited >= _MAX_ENTRIES_VISITED:
                self.truncated = True
                return
            self.visited += 1
            if _is_dir(entry):
                self.n_dirs += 1
                child = _Dir()
                node.entries.append((entry.name, child))
                if depth + 1 < _MAX_DEPTH:
                    queue.append((entry.path, child, depth + 1))
                else:
                    # Deeper levels are neither shown nor counted.
                    self.truncated = True
            else:
                size = _size(entry)
                self.n_files += 1
                self.total_bytes += size
                self.extensions[os.path.splitext(entry.name)[1].lower() or "(none)"] += 1
                node.entries.append((entry.name, size))


def _bounded_tree(root: _Dir) -> list[str]:
    """Render as many whole levels of the tree as fit in ``_MAX_TREE_LINES``."""
    for levels in range(_MAX_DEPTH, 0, -1):
        lines: list[str] = []
        _render(root, levels, "", lines)
        if len(lines) <= _MAX_TREE_LINES:
            break
    return lines


def _render(node: _Dir, levels: int, indent: str, lines: list[str]) -> None:
    """Append ``levels`` levels of ``node``'s entries to ``lines``.

    A directory whose contents are not shown gets a ``...`` line, and a listing
    cut short ends with how many entries it leaves out.
    """
    if node.entries is not None and node.n_entries == 0:
        return
    if node.entries is None or levels == 0:
        lines.append(f"{indent}...")
        return
    shown = node.entries[:_MAX_ENTRIES_PER_DIR]
    for name, child in shown:
        if isinstance(child, _Dir):
            lines.append(f"{indent}{name}/")
            _render(child, levels - 1, indent + "  ", lines)
        else:
            lines.append(f"{indent}{name} ({_human_size(child)})")
    if node.n_entries > len(shown):
        lines.append(f"{indent}... and {node.n_entries - len(shown)} more")


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
            stats = f"At least {stats} (counted from a partial listing; there is more than this)"
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


def store_key_prefix(path: str, store_root: str) -> str:
    """Return the object-key prefix a store-shaped local path mirrors.

    The inverse of mounting a key at ``<store_root>/<key>``: with the store at
    ``/mnt/data``, ``/mnt/data/users/u/datalib/x`` is ``users/u/datalib/x/``.

    Raises:
        ValueError: If ``path`` is not strictly under ``store_root``.
    """
    root = os.path.normpath(store_root)
    norm = os.path.normpath(path)
    if os.path.commonpath([root, norm]) != root or norm == root:
        raise ValueError(f"Data library directory {path!r} is not under {root!r}")
    return f"{os.path.relpath(norm, root)}/"
