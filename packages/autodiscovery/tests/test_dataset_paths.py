"""Tests for local dataset path resolution across the job/subprocess boundary.

These guard the webstack's `data/` upload layout: `get_datasets_fpaths` resolves
dataset names relative to the metadata file's directory, but the actual files
live in a sibling `data/` directory (matching modal's `bucket_path`). The
process/local backends symlink the resolved path into work_dir, so a wrong
resolution produces a dangling symlink (`ls` shows it, `open()` fails).
"""

from __future__ import annotations

from pathlib import Path

from autodiscovery.dataset import resolve_local_dataset_source


def test_resolves_direct_path_when_present(tmp_path: Path) -> None:
    # Colocated layout (CLI): metadata dir contains the file directly.
    f = tmp_path / "data.csv"
    f.write_text("a,b\n1,2\n")
    assert resolve_local_dataset_source(str(f)) == str(f)


def test_falls_back_to_data_subdir(tmp_path: Path) -> None:
    # Webstack layout: metadata dir has a `data/` subdir holding the real file.
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    real = data_dir / "seattle.csv"
    real.write_text("a,b\n1,2\n")

    # The path get_datasets_fpaths would build (metadata-dir relative, no data/).
    resolved = resolve_local_dataset_source(str(tmp_path / "seattle.csv"))

    assert resolved == str(real)
    # And it points at a file that actually exists (no dangling symlink).
    assert Path(resolved).is_file()


def test_returns_absolute_original_when_neither_exists(tmp_path: Path) -> None:
    missing = tmp_path / "nope.csv"
    resolved = resolve_local_dataset_source(str(missing))
    assert resolved == str(missing.resolve()) or resolved == str(missing)
    assert Path(resolved).is_absolute()


def test_prefers_direct_path_over_data_subdir(tmp_path: Path) -> None:
    # If both exist, the direct (metadata-relative) file wins — no surprise remap.
    direct = tmp_path / "x.csv"
    direct.write_text("1")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "x.csv").write_text("2")
    assert resolve_local_dataset_source(str(direct)) == str(direct)
