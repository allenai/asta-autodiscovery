"""Tests for local filesystem run storage."""

from pathlib import Path

import pytest
from autodiscovery_jobs import JobManager
from autodiscovery_jobs.config import JobConfig


@pytest.fixture
def manager(tmp_path: Path) -> JobManager:
    """Create a local-mode manager rooted in a temporary directory."""
    return JobManager(JobConfig(backend="local", local_root=str(tmp_path)))


def test_create_list_and_metadata_round_trip(manager: JobManager) -> None:
    """Create a complete local run layout and round-trip its metadata."""
    run_path = Path(manager.create_job("local", "run-1"))

    assert {path.name for path in run_path.iterdir()} == {"data", "output", "logs"}
    assert manager.list_jobs("local") == ["run-1"]
    assert manager.job_exists("local", "run-1")

    metadata_path = manager.upload_metadata("local", "run-1", {"name": "Local run"})
    assert Path(metadata_path).parent == run_path
    assert manager.get_metadata("local", "run-1") == {"name": "Local run"}


def test_catalog_lists_and_imports_dataset_folders(manager: JobManager, tmp_path: Path) -> None:
    """Create the shared catalog and import catalog or external dataset folders."""
    storage = manager.local_storage
    assert storage is not None
    catalog_dataset = storage.datasets_root / "clinical"
    catalog_dataset.mkdir()
    (catalog_dataset / "patients.csv").write_text("id\n1\n", encoding="utf-8")
    external_dataset = tmp_path / "external-study"
    external_dataset.mkdir()
    (external_dataset / "measurements.csv").write_text("value\n2\n", encoding="utf-8")
    manager.create_job("local", "run-1")

    assert storage.list_datasets() == [
        {"name": "clinical", "file_count": 1, "size_bytes": 5}
    ]
    catalog_files = storage.import_dataset_folder(
        "local", "run-1", dataset_name="clinical"
    )
    external_files = storage.import_dataset_folder(
        "local", "run-1", source_path=str(external_dataset)
    )

    run_data = Path(storage.get_job_path("local", "run-1")) / "data"
    assert catalog_files[0]["name"] == "clinical/patients.csv"
    assert external_files[0]["name"] == "external-study/measurements.csv"
    assert not (run_data / "clinical" / "patients.csv").exists()
    assert not (run_data / "external-study" / "measurements.csv").exists()
    assert storage.get_dataset_source_files("local", "run-1") == {
        "external-study/measurements.csv": (external_dataset / "measurements.csv").resolve()
    }


@pytest.mark.parametrize("jobid", ["", ".", "..", "../outside", "nested/run"])
def test_rejects_run_path_traversal(manager: JobManager, jobid: str) -> None:
    """Reject run IDs that could escape or add hierarchy below the runs root."""
    with pytest.raises(ValueError, match="Invalid job ID"):
        manager.create_job("local", jobid)


def test_rejects_other_users(manager: JobManager) -> None:
    """Prevent hosted identities from crossing into single-user local storage."""
    with pytest.raises(PermissionError, match="configured local user"):
        manager.list_jobs("another-user")


def test_delete_only_removes_selected_run(manager: JobManager) -> None:
    """Delete one run without affecting neighboring local runs."""
    manager.create_job("local", "run-1")
    manager.create_job("local", "run-2")

    manager.delete_job("local", "run-1")

    assert manager.list_jobs("local") == ["run-2"]


def test_upload_and_copy_dataset_files(manager: JobManager, tmp_path: Path) -> None:
    """Upload local files and preserve nested paths when forking run data."""
    source = tmp_path / "source"
    (source / "nested").mkdir(parents=True)
    (source / "table.csv").write_text("value\n1\n", encoding="utf-8")
    (source / "nested" / "notes.txt").write_text("notes", encoding="utf-8")
    manager.create_job("local", "source-run")
    manager.create_job("local", "destination-run")

    data_path = Path(manager.upload_dataset("local", "source-run", source))
    copied = manager.copy_job_data("local", "source-run", "local", "destination-run")

    assert manager.has_data_files("local", "source-run")
    assert (data_path / "table.csv").read_text(encoding="utf-8") == "value\n1\n"
    assert copied == ["nested/notes.txt", "table.csv"]
    destination = Path(manager.get_job_path("local", "destination-run")) / "data"
    assert (destination / "nested" / "notes.txt").read_text(encoding="utf-8") == "notes"


def test_upload_rejects_unsafe_filename(manager: JobManager, tmp_path: Path) -> None:
    """Prevent multipart filenames from escaping the run data directory."""
    source = tmp_path / "source.csv"
    source.write_text("value\n1\n", encoding="utf-8")
    manager.create_job("local", "run-1")

    with pytest.raises(ValueError, match="Invalid filename"):
        manager.upload_dataset("local", "run-1", source, remote_name="../outside.csv")


def test_upload_preserves_valid_relative_path(manager: JobManager, tmp_path: Path) -> None:
    """Preserve folder structure selected by the local browser picker."""
    source = tmp_path / "source.csv"
    source.write_text("value\n1\n", encoding="utf-8")
    run_path = Path(manager.create_job("local", "run-1"))

    manager.upload_dataset(
        "local", "run-1", source, remote_name="selected-folder/nested/source.csv"
    )

    assert (run_path / "data" / "selected-folder" / "nested" / "source.csv").is_file()


def test_soft_delete_removes_data_and_preserves_results(
    manager: JobManager, tmp_path: Path
) -> None:
    """Preserve local run artifacts while removing uploaded data."""
    source = tmp_path / "source.csv"
    source.write_text("value\n1\n", encoding="utf-8")
    run_path = Path(manager.create_job("local", "run-1"))
    manager.upload_dataset("local", "run-1", source)
    manager.upload_metadata("local", "run-1", {"name": "Run"})
    (run_path / "output" / "report.html").write_text("report", encoding="utf-8")

    result = manager.soft_delete_job("local", "run-1")

    assert result["status"] == "DELETED"
    assert result["deleted_at"]
    assert not (run_path / "data" / "source.csv").exists()
    assert (run_path / "metadata.json").is_file()
    assert (run_path / "output" / "report.html").is_file()
