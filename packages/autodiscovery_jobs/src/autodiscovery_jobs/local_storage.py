"""Filesystem storage for single-user local AutoDiscovery runs."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import JobConfig


class LocalStorage:
    """Store local-mode runs under a configured application data root."""

    def __init__(self, config: JobConfig) -> None:
        """Initialize storage without creating the root until it is needed."""
        self.config = config
        self.root = Path(config.local_root).expanduser().resolve()
        self.runs_root = self.root / "runs"
        self.datasets_root = self.root / "data"
        self.datasets_root.mkdir(parents=True, exist_ok=True)

    def _validate_user(self, userid: str) -> None:
        if userid != self.config.local_user_id:
            raise PermissionError("Local mode only permits the configured local user")

    @staticmethod
    def _validate_segment(value: str, label: str) -> str:
        if not value or value in {".", ".."} or Path(value).name != value:
            raise ValueError(f"Invalid {label}")
        if os.sep in value or (os.altsep and os.altsep in value):
            raise ValueError(f"Invalid {label}")
        return value

    @classmethod
    def _validate_relative_path(cls, value: str, label: str) -> Path:
        normalized = value.replace("\\", "/")
        path = Path(normalized)
        if path.is_absolute() or not path.parts:
            raise ValueError(f"Invalid {label}")
        for part in path.parts:
            cls._validate_segment(part, label)
        return path

    def _dataset_sources_path(self, userid: str, jobid: str) -> Path:
        return self.get_job_path(userid, jobid) / ".dataset-sources.json"

    def get_dataset_source_files(self, userid: str, jobid: str) -> dict[str, Path]:
        """Return validated referenced source files for a local run."""
        manifest_path = self._dataset_sources_path(userid, jobid)
        if not manifest_path.is_file():
            return {}
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        result: dict[str, Path] = {}
        for relative_name, source_value in manifest.get("files", {}).items():
            relative_path = self._validate_relative_path(relative_name, "dataset path")
            source = Path(source_value)
            if source.is_symlink() or not source.is_file():
                raise FileNotFoundError(f"Referenced dataset file is unavailable: {relative_name}")
            result[relative_path.as_posix()] = source.resolve()
        return result

    def _write_dataset_sources(
        self, userid: str, jobid: str, source_files: dict[str, Path]
    ) -> None:
        """Atomically persist trusted source references outside renderer-visible metadata."""
        manifest_path = self._dataset_sources_path(userid, jobid)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=manifest_path.parent,
            prefix=".dataset-sources-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            json.dump(
                {"files": {name: str(path.resolve()) for name, path in source_files.items()}},
                temp_file,
                indent=2,
            )
            temp_path = Path(temp_file.name)
        temp_path.replace(manifest_path)

    def get_user_path(self, userid: str) -> str:
        """Return the local runs directory for the configured user."""
        self._validate_user(userid)
        return str(self.runs_root)

    def list_user_ids(self) -> list[str]:
        """Return the configured user when local run storage exists."""
        return [self.config.local_user_id] if self.runs_root.is_dir() else []

    def list_jobs(self, userid: str) -> list[str]:
        """List run IDs owned by the configured local user."""
        self._validate_user(userid)
        if not self.runs_root.is_dir():
            return []
        return sorted(path.name for path in self.runs_root.iterdir() if path.is_dir())

    def list_datasets(self) -> list[dict[str, Any]]:
        """List immediate folders in the shared local dataset catalog."""
        datasets: list[dict[str, Any]] = []
        for dataset_path in sorted(
            self.datasets_root.iterdir(), key=lambda path: path.name.lower()
        ):
            if not dataset_path.is_dir() or dataset_path.is_symlink():
                continue
            files = [path for path in dataset_path.rglob("*") if path.is_file()]
            datasets.append(
                {
                    "name": dataset_path.name,
                    "file_count": len(files),
                    "size_bytes": sum(path.stat().st_size for path in files),
                }
            )
        return datasets

    def import_dataset_folder(
        self,
        userid: str,
        jobid: str,
        *,
        dataset_name: str | None = None,
        source_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """Reference a catalog dataset or external folder from one local run."""
        if bool(dataset_name) == bool(source_path):
            raise ValueError("Provide either a dataset name or folder path")
        if dataset_name:
            safe_name = self._validate_segment(dataset_name, "dataset name")
            source = self.datasets_root / safe_name
        else:
            source = Path(source_path or "").expanduser()
            safe_name = source.name
            self._validate_segment(safe_name, "dataset name")
        if source.is_symlink() or not source.is_dir():
            raise ValueError("Dataset folder does not exist or is a symbolic link")

        run_data = self.get_job_path(userid, jobid) / "data"
        if not run_data.is_dir():
            raise FileNotFoundError(f"Run does not exist: {jobid}")
        source_files: list[Path] = []
        for file_path in source.rglob("*"):
            if file_path.is_symlink():
                raise ValueError("Dataset directories may not contain symbolic links")
            if file_path.is_file():
                source_files.append(file_path)
        if not source_files:
            raise ValueError("Dataset folder does not contain any files")

        for existing in run_data.iterdir():
            if existing.is_dir():
                shutil.rmtree(existing)
            else:
                existing.unlink()
        imported: list[dict[str, Any]] = []
        source_manifest: dict[str, Path] = {}
        for file_path in source_files:
            relative_path = Path(safe_name) / file_path.relative_to(source)
            source_manifest[relative_path.as_posix()] = file_path.resolve()
            imported.append(
                {
                    "name": relative_path.as_posix(),
                    "content_type": "application/octet-stream",
                    "file_size_bytes": file_path.stat().st_size,
                }
            )
        self._write_dataset_sources(userid, jobid, source_manifest)
        return sorted(imported, key=lambda item: item["name"])

    def get_job_path(self, userid: str, jobid: str) -> Path:
        """Return a validated path below the local runs root."""
        self._validate_user(userid)
        safe_jobid = self._validate_segment(jobid, "job ID")
        return self.runs_root / safe_jobid

    def job_exists(self, userid: str, jobid: str) -> bool:
        """Return whether the local run directory exists."""
        return self.get_job_path(userid, jobid).is_dir()

    def create_job(self, userid: str, jobid: str, overwrite: bool = False) -> str:
        """Create the standard directory layout for one local run."""
        run_path = self.get_job_path(userid, jobid)
        if run_path.exists() and not overwrite:
            raise FileExistsError(f"Run already exists: {jobid}")
        for name in ("data", "output", "logs"):
            (run_path / name).mkdir(parents=True, exist_ok=overwrite)
        return str(run_path)

    def delete_job(self, userid: str, jobid: str) -> None:
        """Delete one validated local run directory."""
        run_path = self.get_job_path(userid, jobid)
        if run_path.exists():
            shutil.rmtree(run_path)

    def soft_delete_job(self, userid: str, jobid: str) -> dict[str, Any]:
        """Remove uploaded data while preserving local metadata and results."""
        run_path = self.get_job_path(userid, jobid)
        if not run_path.is_dir():
            raise FileNotFoundError(f"Run does not exist: {jobid}")
        data_path = run_path / "data"
        deleted_files: list[str] = []
        if data_path.is_dir():
            deleted_files = sorted(
                str(path.relative_to(run_path)) for path in data_path.rglob("*") if path.is_file()
            )
            shutil.rmtree(data_path)
        data_path.mkdir()
        self._dataset_sources_path(userid, jobid).unlink(missing_ok=True)
        preserved_files = sum(1 for path in run_path.rglob("*") if path.is_file())
        return {
            "deleted_files": deleted_files,
            "preserved_files": preserved_files,
            "status": "DELETED",
            "deleted_at": datetime.now(UTC).isoformat(),
        }

    def upload_dataset(
        self,
        userid: str,
        jobid: str,
        local_path: Path,
        remote_name: str | None = None,
    ) -> str:
        """Copy dataset files into a local run without following symlinks."""
        source = Path(local_path)
        data_path = self.get_job_path(userid, jobid) / "data"
        if not data_path.is_dir():
            raise FileNotFoundError(f"Run does not exist: {jobid}")
        if source.is_symlink():
            raise ValueError("Dataset source may not be a symbolic link")
        self._dataset_sources_path(userid, jobid).unlink(missing_ok=True)
        if source.is_file():
            relative_path = self._validate_relative_path(
                remote_name or source.name, "filename"
            )
            destination = data_path / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        elif source.is_dir():
            for file_path in source.rglob("*"):
                if file_path.is_symlink():
                    raise ValueError("Dataset directories may not contain symbolic links")
                if file_path.is_file():
                    relative_path = file_path.relative_to(source)
                    destination = data_path / relative_path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(file_path, destination)
        else:
            raise FileNotFoundError(f"Dataset path does not exist: {source}")
        return str(data_path)

    def has_data_files(self, userid: str, jobid: str) -> bool:
        """Return whether a local run contains at least one dataset file."""
        if self.get_dataset_source_files(userid, jobid):
            return True
        data_path = self.get_job_path(userid, jobid) / "data"
        return data_path.is_dir() and any(path.is_file() for path in data_path.rglob("*"))

    def copy_job_data(
        self,
        source_userid: str,
        source_jobid: str,
        dest_userid: str,
        dest_jobid: str,
    ) -> list[str]:
        """Copy dataset files between validated local runs."""
        source_data = self.get_job_path(source_userid, source_jobid) / "data"
        destination_data = self.get_job_path(dest_userid, dest_jobid) / "data"
        if not source_data.is_dir() or not destination_data.is_dir():
            raise FileNotFoundError("Source and destination runs must exist")
        source_references = self.get_dataset_source_files(source_userid, source_jobid)
        if source_references:
            self._write_dataset_sources(dest_userid, dest_jobid, source_references)
            return sorted(source_references)
        copied: list[str] = []
        for source in source_data.rglob("*"):
            if source.is_symlink():
                raise ValueError("Dataset directories may not contain symbolic links")
            if source.is_file():
                relative_path = source.relative_to(source_data)
                destination = destination_data / relative_path
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                copied.append(str(relative_path))
        return sorted(copied)

    def upload_metadata(self, userid: str, jobid: str, metadata: dict[str, Any]) -> str:
        """Atomically write run metadata as JSON."""
        run_path = self.get_job_path(userid, jobid)
        if not run_path.is_dir():
            raise FileNotFoundError(f"Run does not exist: {jobid}")
        destination = run_path / "metadata.json"
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=run_path,
            prefix=".metadata-",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            json.dump(metadata, temp_file, indent=2)
            temp_path = Path(temp_file.name)
        temp_path.replace(destination)
        return str(destination)

    def get_metadata(self, userid: str, jobid: str) -> dict[str, Any]:
        """Read run metadata, returning an empty dictionary when absent."""
        metadata_path = self.get_job_path(userid, jobid) / "metadata.json"
        if not metadata_path.is_file():
            return {}
        with metadata_path.open(encoding="utf-8") as metadata_file:
            value = json.load(metadata_file)
        if not isinstance(value, dict):
            raise ValueError("Run metadata must be a JSON object")
        return value

    def get_results(self, userid: str, jobid: str) -> list[str]:
        """List files produced under a local run's output directory."""
        output_path = self.get_job_path(userid, jobid) / "output"
        if not output_path.is_dir():
            return []
        return sorted(
            str(path.relative_to(output_path))
            for path in output_path.rglob("*")
            if path.is_file()
        )

    def read_rich_outputs(
        self,
        userid: str,
        jobid: str,
        level: int,
        index: int,
    ) -> list[dict[str, Any]]:
        """Read rich output bundles for one local experiment node."""
        rich_path = (
            self.get_job_path(userid, jobid)
            / "output"
            / "rich_outputs"
            / f"ro_{level}_{index}.json"
        )
        if not rich_path.is_file():
            return []
        try:
            with rich_path.open(encoding="utf-8") as rich_file:
                value = json.load(rich_file)
        except (OSError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []
