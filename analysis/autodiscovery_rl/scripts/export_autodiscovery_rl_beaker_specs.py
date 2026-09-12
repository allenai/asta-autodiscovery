#!/usr/bin/env python3
"""Recover normalized Beaker v2 YAML specs for indexed slime RL experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPORTED_REGISTRY = ROOT / "registry" / "source-workspace-registry.json"
DEFAULT_REGISTRY = (
    EXPORTED_REGISTRY
    if EXPORTED_REGISTRY.exists()
    else ROOT / "output" / "autodiscovery-rl-artifact-registry" / "artifact-registry.json"
)
DEFAULT_OUTPUT = (
    ROOT / "launch-specs" / "recovered-beaker-rl-specs"
    if EXPORTED_REGISTRY.exists()
    else ROOT / "logs" / "launch-specs" / "recovered-beaker-rl-specs"
)
BEAKER = Path.home() / ".local" / "bin" / "beaker"
SENSITIVE_VALUE = re.compile(
    r"(?:sk-(?:proj-)?[A-Za-z0-9_-]{16,}|wandb_v1_[A-Za-z0-9_-]{16,}|"
    r"ghp_[A-Za-z0-9]{16,}|github_pat_[A-Za-z0-9_]{16,}|AKIA[A-Z0-9]{16}|"
    r"AIza[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{16,})"
)


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return normalized[:120] or "unnamed"


def parse_json_output(value: str) -> Any:
    """Parse CLI JSON even if a warning line precedes the document."""
    starts = [position for marker in ("[", "{") if (position := value.find(marker)) >= 0]
    if not starts:
        raise ValueError("Beaker CLI returned no JSON document")
    return json.loads(value[min(starts) :])


def yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def yaml_lines(value: Any, indent: int = 0) -> list[str]:
    prefix = " " * indent
    if isinstance(value, dict):
        lines: list[str] = []
        for key, item in value.items():
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.extend(yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {yaml_scalar(item)}")
        return lines
    if isinstance(value, list):
        lines = []
        for item in value:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.extend(yaml_lines(item, indent + 2))
            else:
                lines.append(f"{prefix}- {yaml_scalar(item)}")
        return lines
    return [f"{prefix}{yaml_scalar(value)}"]


def duration_from_nanoseconds(value: Any) -> Any:
    if not isinstance(value, int):
        return value
    seconds = value // 1_000_000_000
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours}h{minutes}m{seconds}s" if hours else f"{minutes}m{seconds}s" if minutes else f"{seconds}s"


def recover_from_result_job(run: dict[str, Any]) -> str | None:
    for dataset_id in run.get("result_dataset_ids", []):
        dataset = subprocess.run(
            [str(BEAKER), "dataset", "inspect", dataset_id, "--format", "json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if dataset.returncode:
            continue
        dataset_items = parse_json_output(dataset.stdout)
        execution_id = dataset_items[0].get("sourceExecution") if dataset_items else None
        if not execution_id:
            continue
        job = subprocess.run(
            [str(BEAKER), "job", "inspect", execution_id, "--format", "json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if job.returncode:
            continue
        job_items = parse_json_output(job.stdout)
        if not job_items:
            continue
        task_spec = job_items[0]["execution"]["spec"]
        task_spec["envVars"] = [
            item for item in task_spec.get("envVars", []) if not str(item.get("name", "")).startswith("BEAKER_")
        ]
        task_spec["timeout"] = duration_from_nanoseconds(task_spec.get("timeout"))
        if "context" in task_spec:
            task_spec["context"]["minRuntime"] = duration_from_nanoseconds(task_spec["context"].get("minRuntime"))
        payload = {
            "version": "v2",
            "description": run.get("name") or f"Recovered experiment {run['id']}",
            "tasks": [task_spec],
        }
        return "\n".join(yaml_lines(payload)) + "\n"
    return None


def recover(run: dict[str, Any]) -> tuple[dict[str, Any], str | None, str | None, str | None]:
    experiment_id = run["id"]
    result = subprocess.run(
        [str(BEAKER), "experiment", "spec", experiment_id, "--version", "v2"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode:
        fallback = recover_from_result_job(run)
        if fallback:
            if SENSITIVE_VALUE.search(fallback):
                return run, None, None, "refused: job-recovered spec contains a credential-like value"
            return run, fallback, "result dataset → retained source job", None
        return run, None, None, (result.stderr or result.stdout).strip()
    spec = result.stdout
    if SENSITIVE_VALUE.search(spec):
        return run, None, None, "refused: normalized spec contains a credential-like value"
    return run, spec, "beaker experiment spec --version v2", None


def is_slime_rl_spec(spec: str) -> bool:
    slime_marker = any(
        marker in spec
        for marker in ("slimerl/slime", "/slime-repo", "sijial430/slime")
    )
    rl_marker = any(
        marker in spec
        for marker in (
            "ADVANTAGE_ESTIMATOR",
            "N_SAMPLES_PER_PROMPT",
            "beaker_fmt_ablation_entry.sh",
            "train_grpo.sh",
            "autodiscovery_rl",
        )
    )
    return slime_marker and rl_marker


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()

    registry = json.loads(args.registry.read_text())
    runs = registry["external_experiments"]
    recovered: list[tuple[dict[str, Any], str, str]] = []
    failures: list[dict[str, str]] = []
    skipped: list[dict[str, str | None]] = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(recover, run): run for run in runs}
        for future in as_completed(futures):
            run, spec, source, error = future.result()
            if error:
                failures.append({"experiment_id": run["id"], "error": error})
            elif spec and is_slime_rl_spec(spec):
                recovered.append((run, spec, source or "unknown"))
            else:
                skipped.append(
                    {
                        "experiment_id": run["id"],
                        "name": run.get("name"),
                        "reason": "normalized spec did not contain both slime and RL launch markers",
                    }
                )

    args.output.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for run, spec, source in sorted(recovered, key=lambda item: (str(item[0].get("family") or ""), item[0]["id"])):
        family = slug(str(run.get("family") or "uncategorized"))
        filename = f"{run['id']}--{slug(str(run.get('name') or run['id']))}.yaml"
        path = args.output / "specs" / family / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(spec)
        records.append(
            {
                "experiment_id": run["id"],
                "name": run.get("name"),
                "family": run.get("family"),
                "status": run.get("status"),
                "exit_code": run.get("exit_code"),
                "beaker_url": run.get("beaker_url"),
                "source": source,
                "path": path.relative_to(args.output).as_posix(),
                "size_bytes": len(spec.encode()),
                "sha256": hashlib.sha256(spec.encode()).hexdigest(),
                "task_count": len(
                    re.findall(r"^  -(?: name:|\n    name:)", spec, flags=re.MULTILINE)
                ),
            }
        )

    manifest = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_registry": (
            args.registry.resolve().relative_to(ROOT.resolve()).as_posix()
            if args.registry.resolve().is_relative_to(ROOT.resolve())
            else str(args.registry)
        ),
        "source_registry_generated_at": registry.get("generated_at"),
        "indexed_experiments_checked": len(runs),
        "slime_rl_specs_recovered": len(records),
        "failed_retrievals": failures,
        "skipped_non_slime_specs": skipped,
        "specs": records,
    }
    (args.output / "index.json").write_text(json.dumps(manifest, indent=2) + "\n")

    by_family: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for record in records:
        family = str(record["family"] or "uncategorized")
        by_family[family] = by_family.get(family, 0) + 1
        source = str(record["source"])
        by_source[source] = by_source.get(source, 0) + 1
    lines = [
        "# Recovered slime RL Beaker specs",
        "",
        f"Recovered {len(records)} normalized Beaker v2 YAML launch specs from "
        f"{len(runs)} indexed AutoDiscovery-RL experiments on {manifest['generated_at']}.",
        "",
        f"{by_source.get('beaker experiment spec --version v2', 0)} specs are the normalized, server-retained "
        "experiment definitions returned by `beaker experiment spec`. "
        f"{by_source.get('result dataset → retained source job', 0)} deleted experiment was recovered from its "
        "result dataset's retained source job, with Beaker-injected environment variables removed. "
        "Beaker secret references are retained by name; credential values are neither returned nor stored. "
        "The export refuses to write a spec if it contains a credential-like value.",
        "",
        "## Families",
        "",
        "| Family | Specs |",
        "|---|---:|",
    ]
    lines.extend(f"| {family} | {count} |" for family, count in sorted(by_family.items()))
    lines.extend(
        [
            "",
            "## Index",
            "",
            "[`index.json`](index.json) records every experiment ID, name, family, final indexed status, "
            "YAML path, byte size, SHA-256, task count, and Beaker URL.",
            "",
            f"Retrieval failures: {len(failures)}. Non-slime specs skipped: {len(skipped)}.",
            "",
        ]
    )
    (args.output / "README.md").write_text("\n".join(lines))
    print(
        json.dumps(
            {
                "checked": len(runs),
                "recovered": len(records),
                "failures": len(failures),
                "skipped": len(skipped),
                "families": by_family,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
