"""Local subprocess job backend for single-user AutoDiscovery deployments."""

from __future__ import annotations

import json
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

from ..local_runner import LocalProcessRunner
from ..local_storage import LocalStorage
from .base import JobBackend


class LocalProcessBackend(JobBackend):
    """Launch AutoDiscovery workers directly as managed local subprocesses."""

    def __init__(self, config) -> None:
        """Initialize local filesystem storage and process lifecycle management."""
        super().__init__(config)
        self.storage = LocalStorage(config)
        self.runner = LocalProcessRunner(config)

    @staticmethod
    def _prepare_runtime_view(
        run_path: Path,
        metadata: dict[str, Any],
        source_files: dict[str, Path] | None = None,
    ) -> Path:
        """Expose declared datasets at stable basenames in the worker directory."""
        data_path = (run_path / "data").resolve()
        work_path = run_path / "work"
        work_path.mkdir(parents=True, exist_ok=True)
        runtime_metadata = json.loads(json.dumps(metadata))
        source_files = source_files or {}
        aliases: dict[str, Path] = {}

        for dataset in runtime_metadata.get("datasets", []):
            relative_name = str(dataset.get("name") or "")
            source = source_files.get(relative_name)
            if source is None:
                source = (data_path / relative_name).resolve()
                if source == data_path or data_path not in source.parents:
                    raise ValueError(f"Dataset path escapes the local run: {relative_name}")
            if not source.is_file() or source.is_symlink():
                raise FileNotFoundError(f"Local dataset file not found: {relative_name}")
            alias = source.name
            previous = aliases.get(alias)
            if previous is not None and previous != source:
                raise ValueError(f"Local dataset filenames must be unique: {alias}")
            aliases[alias] = source
            dataset["name"] = alias

        for alias, source in aliases.items():
            destination = work_path / alias
            if destination.is_symlink() or destination.exists():
                raise FileExistsError(f"Local runtime dataset alias already exists: {alias}")
            shutil.copy2(source, destination)
            destination.chmod(
                destination.stat().st_mode
                & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH)
            )

        runtime_metadata_path = work_path / ".autodiscovery-metadata.json"
        runtime_metadata_path.write_text(json.dumps(runtime_metadata, indent=2), encoding="utf-8")
        return runtime_metadata_path

    def run_job(
        self,
        userid: str,
        jobid: str,
        n_experiments: int | None = None,
        model: str | None = None,
        belief_model: str | None = None,
        temperature: float | None = None,
        belief_temperature: float | None = None,
        k_experiments: int | None = None,
        mcts_selection: str | None = None,
        reasoning_effort: str | None = None,
        exploration_weight: float | None = None,
        code_timeout: int | None = None,
        n_warmstart: int | None = None,
        **kwargs: Any,
    ) -> str:
        """Launch the local worker and return its persistent execution ID."""
        if n_experiments is None:
            raise ValueError("n_experiments is required to run a job")
        run_path = self.storage.get_job_path(userid, jobid)
        metadata = self.storage.get_metadata(userid, jobid)
        if not metadata:
            raise FileNotFoundError(f"Run metadata not found: {jobid}")
        runtime_metadata = self._prepare_runtime_view(
            run_path,
            metadata,
            self.storage.get_dataset_source_files(userid, jobid),
        )
        command = [
            sys.executable,
            "-m",
            "autodiscovery.local_worker",
            f"--dataset_metadata={runtime_metadata}",
            f"--out_dir={run_path / 'output'}",
            f"--n_experiments={n_experiments}",
            f"--work_dir={run_path / 'work'}",
            f"--backend={self.config.code_execution_backend}",
            "--no-timestamp_dir",
        ]
        optional_args = {
            "model": model,
            "belief_model": belief_model,
            "temperature": temperature,
            "belief_temperature": belief_temperature,
            "k_experiments": k_experiments,
            "mcts_selection": mcts_selection,
            "reasoning_effort": reasoning_effort,
            "exploration_weight": exploration_weight,
            "code_timeout": code_timeout,
            "n_warmstart": n_warmstart,
            **kwargs,
        }
        for key, value in optional_args.items():
            if value is None:
                continue
            if isinstance(value, bool):
                command.append(f"--{key}" if value else f"--no-{key}")
            else:
                command.append(f"--{key}={value}")
        return self.runner.start(
            command,
            run_id=jobid,
            cwd=run_path,
            log_path=run_path / "logs" / "engine.log",
            env=dict(os.environ),
        )

    def get_job_status(self, execution_id: str) -> dict[str, Any]:
        """Return the persisted status for a local execution."""
        return self.runner.get_status(execution_id)

    def cancel_job(self, execution_id: str) -> None:
        """Terminate a local execution process group."""
        self.runner.cancel(execution_id)

    def get_job_logs(self, execution_id: str | None = None, limit: int = 50) -> list[str]:
        """Return recent combined output for a local execution."""
        if execution_id is None:
            raise ValueError("Local logs require an execution ID")
        return self.runner.get_logs(execution_id, limit)
