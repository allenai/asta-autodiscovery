"""Tests for data-library directories: manifests, prompts, and sandbox mounts."""

from __future__ import annotations

import json

import pytest
from autodiscovery import datalib
from autodiscovery.agents import get_agents
from autodiscovery.args import ArgParser
from autodiscovery.dataset import get_load_dataset_experiment

_MODEL = "openai/gpt-4o"


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "mnt" / "data" / "users" / "u1" / "datalib" / "census"
    (root / "2020").mkdir(parents=True)
    (root / "README.md").write_text("# Census\nOne CSV per year.")
    (root / "2020" / "part-0.csv").write_text("a,b\n1,2\n")
    (root / "2020" / "part-1.csv").write_text("a,b\n3,4\n")
    (root / "codebook.json").write_text("{}")
    return root


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def test_manifest_reads_readme_and_tallies_files(library):
    m = datalib.build_manifest(str(library))

    assert m.readme == "# Census\nOne CSV per year."
    assert m.n_files == 4
    assert m.n_dirs == 1
    assert m.extensions == {".csv": 2, ".json": 1, ".md": 1}
    assert m.tree[0] == "2020/"
    assert m.tree[1].startswith("  part-0.csv (")
    assert not m.truncated
    json.dumps(m.to_dict())  # provenance copy must be serializable


def test_manifest_without_readme(library):
    (library / "README.md").unlink()
    m = datalib.build_manifest(str(library))

    assert m.readme is None
    assert "(No README.md provided.)" in datalib.describe([m])


def test_manifest_bounds_what_it_shows(tmp_path, monkeypatch):
    monkeypatch.setattr(datalib, "_MAX_ENTRIES_PER_DIR", 3)
    for i in range(10):
        (tmp_path / f"f{i}.parquet").write_text("x")

    m = datalib.build_manifest(str(tmp_path))

    assert m.n_files == 10  # every file is counted
    assert len(m.tree) == 4  # only three are listed, then a summary line
    assert m.tree[-1] == "... and 7 more"


def test_manifest_flags_a_partial_walk(tmp_path, monkeypatch):
    monkeypatch.setattr(datalib, "_MAX_DEPTH", 1)
    (tmp_path / "deep").mkdir()
    (tmp_path / "deep" / "x.csv").write_text("x")

    m = datalib.build_manifest(str(tmp_path))

    assert m.truncated
    assert m.n_files == 0
    assert "partial listing" in datalib.describe([m])


def test_manifest_requires_a_directory(tmp_path):
    with pytest.raises(FileNotFoundError):
        datalib.build_manifest(str(tmp_path / "missing"))


# ---------------------------------------------------------------------------
# Store path -> gs:// source
# ---------------------------------------------------------------------------


def test_gs_source_maps_the_path_by_key():
    assert datalib.gs_source("/mnt/data/users/u1/datalib/census", "/mnt/data", "gs://bucket") == (
        "bucket",
        "users/u1/datalib/census/",
    )


def test_gs_source_with_a_prefixed_store_uri():
    assert datalib.gs_source("/mnt/data/users/u1/datalib/x", "/mnt/data/", "gs://b/root/") == (
        "b",
        "root/users/u1/datalib/x/",
    )


@pytest.mark.parametrize(
    "path,root,uri",
    [
        ("/elsewhere/x", "/mnt/data", "gs://b"),
        ("/mnt/data/../etc", "/mnt/data", "gs://b"),
        ("/mnt/data", "/mnt/data", "gs://b"),
        ("/mnt/data/x", "/mnt/data", "s3://b"),
    ],
)
def test_gs_source_rejects_paths_outside_the_store(path, root, uri):
    with pytest.raises(ValueError):
        datalib.gs_source(path, root, uri)


# ---------------------------------------------------------------------------
# First experiment
# ---------------------------------------------------------------------------


def _metadata(tmp_path, datasets):
    path = tmp_path / "metadata.json"
    path.write_text(json.dumps({"description": "", "datasets": datasets}))
    return str(path)


def test_load_experiment_unchanged_without_datalib(tmp_path):
    meta = _metadata(tmp_path, [{"name": "a.csv", "description": "A"}])
    exp = get_load_dataset_experiment([str(tmp_path / "a.csv")], meta)
    plan = exp["experiment_plan"]

    assert plan["steps"] == (
        "1. Load the dataset(s) at ['a.csv'].\n2. Generate summary statistics for the dataset(s)."
    )
    assert "DATA LIBRARY" not in plan["objective"]


def test_load_experiment_with_datalib_only(tmp_path, library):
    meta = _metadata(tmp_path, [])
    m = datalib.build_manifest(str(library))
    plan = get_load_dataset_experiment([], meta, datalib_manifests=[m])["experiment_plan"]

    assert plan["steps"].startswith("1. Survey the read-only data library")
    assert "Load the dataset(s) at []" not in plan["steps"]
    assert str(library) in plan["objective"]
    assert "One CSV per year." in plan["objective"]
    # No empty dataset-metadata section when nothing was uploaded.
    assert "DATASET DESCRIPTION" not in plan["objective"]


def test_load_experiment_with_uploads_and_datalib(tmp_path, library):
    meta = _metadata(tmp_path, [{"name": "a.csv", "description": "A"}])
    m = datalib.build_manifest(str(library))
    plan = get_load_dataset_experiment(
        [str(tmp_path / "a.csv")], meta, run_eda=True, datalib_manifests=[m]
    )["experiment_plan"]

    lines = plan["steps"].splitlines()
    assert lines[0].startswith("1. Load the dataset(s)")
    assert lines[1].startswith("2. Survey")
    assert lines[2].startswith("3. Generate")
    assert lines[3].startswith("4. Perform some exploratory")
    assert "DATASET DESCRIPTION" in plan["objective"]
    assert "DATA LIBRARY" in plan["objective"]


# ---------------------------------------------------------------------------
# CLI and agents
# ---------------------------------------------------------------------------


def test_cli_accepts_repeated_datalib_dirs():
    args = ArgParser().parse_args(
        [
            "--dataset_metadata=m.json",
            "--out_dir=o",
            "--work_dir=w",
            "--n_experiments=1",
            "--datalib_dir=/mnt/data/users/u/datalib/a",
            "--datalib_dir=/mnt/data/users/u/datalib/b",
        ]
    )
    assert args.datalib_dir == ["/mnt/data/users/u/datalib/a", "/mnt/data/users/u/datalib/b"]
    assert (
        ArgParser()
        .parse_args(
            ["--dataset_metadata=m.json", "--out_dir=o", "--work_dir=w", "--n_experiments=1"]
        )
        .datalib_dir
        == []
    )


def _system_messages(agents):
    return {name: a.system_message for name, a in agents.items() if a.llm_config is not False}


def test_prompts_unchanged_without_datalib(tmp_path):
    base = _system_messages(get_agents(str(tmp_path), model_name=_MODEL, vision_model=_MODEL))
    with_empty = _system_messages(
        get_agents(str(tmp_path), model_name=_MODEL, vision_model=_MODEL, datalib_dirs=[])
    )
    assert base == with_empty
    assert not any("data library" in m for m in base.values())


def test_prompts_name_the_datalib_paths(tmp_path):
    path = "/mnt/data/users/u1/datalib/census"
    messages = _system_messages(
        get_agents(str(tmp_path), model_name=_MODEL, vision_model=_MODEL, datalib_dirs=[path])
    )
    for name in ("experiment_generator", "experiment_programmer", "experiment_reviser"):
        assert path in messages[name], name
        assert "never write to them" in messages[name]


class _FakeModalExecutor:
    def __init__(self, **kwargs):
        self.shares = []

    async def add_shares(self, *shares):
        self.shares.extend(shares)


@pytest.fixture
def fake_modal(monkeypatch):
    import asta_sandbox.backends.modal_ephemeral as modal_ephemeral
    import autodiscovery_modal.ipython_session as ipython_session
    import modal

    created = []

    def make_executor(**kwargs):
        executor = _FakeModalExecutor(**kwargs)
        created.append(executor)
        return executor

    monkeypatch.setattr(modal_ephemeral, "ModalEphemeralExecutor", make_executor)
    monkeypatch.setattr(ipython_session, "build_sandbox_image", lambda **_: object())
    monkeypatch.setattr(modal.Secret, "from_name", staticmethod(lambda name: name))
    return created


def test_modal_mounts_datalib_dirs_read_only_at_the_same_path(tmp_path, fake_modal):
    path = "/mnt/data/users/u1/datalib/census"
    get_agents(
        str(tmp_path),
        model_name=_MODEL,
        vision_model=_MODEL,
        backend="modal",
        bucket_path="gs://bucket/users/u1/jobs/j1/data",
        datalib_dirs=[path],
        store_root="/mnt/data",
        store_uri="gs://bucket",
    )

    uploads, library_share = fake_modal[0].shares
    assert uploads.dest == "/data"  # unchanged
    assert library_share.dest == path
    assert library_share.bucket == "bucket"
    assert library_share.key_prefix == "users/u1/datalib/census/"
    assert library_share.read_only is True


def test_modal_datalib_requires_the_store_mapping(tmp_path, fake_modal):
    with pytest.raises(ValueError, match="store_root and store_uri"):
        get_agents(
            str(tmp_path),
            model_name=_MODEL,
            vision_model=_MODEL,
            backend="modal",
            bucket_path="gs://bucket/users/u1/jobs/j1/data",
            datalib_dirs=["/mnt/data/users/u1/datalib/census"],
        )
