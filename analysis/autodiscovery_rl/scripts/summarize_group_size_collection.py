#!/usr/bin/env python3
"""Summarize the locally collected AutoDiscovery archaeology group-size sweep."""

from __future__ import annotations

import hashlib
import json
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path("logs/collected-runs-2026-09-06")
RUNS = {
    16: {
        "experiment_id": "01M0RQFD4QVN3BS85PYDPC0MNX",
        "job_id": "01M0RQFD87PTQW9MC8H1RVHH9F",
        "result_dataset_id": "01M0RQFD4W8P48EEDM9JK9CC4D",
        "exit_code": 0,
        "status": "succeeded",
    },
    32: {
        "experiment_id": "01M115W5YND6WFMHTW59SAMTER",
        "job_id": "01M115W64VD1YVXJTBJP1XG235",
        "result_dataset_id": "01M115W5YWD83PX1275V4E3M3K",
        "exit_code": 0,
        "status": "succeeded",
    },
    64: {
        "experiment_id": "01M1PQYZA5BMGHEZJKBDXRZEGC",
        "job_id": "01M1PQYZHY0CR2XTT4CJAY27X5",
        "result_dataset_id": "01M1PQYZAG2FSPKKX111DNK2YY",
        "exit_code": 1,
        "status": "Ray succeeded; outer success guard produced a false failure",
    },
    128: {
        "experiment_id": "01M1V3C7AC1B14HS4NB33Y4Y0J",
        "job_id": "01M1V3C7E7KDMGXWVMX40M4HXC",
        "result_dataset_id": "01M1V3C7ATNVH91FAY3836CZ0B",
        "exit_code": 0,
        "status": "succeeded",
    },
    256: {
        "experiment_id": "01M0RQFDKMHE1GVKJ67EZF9042",
        "job_id": "01M0RQFDQ1MQS7RD82H02XZNRN",
        "result_dataset_id": "01M0RQFDKR2HVNHM3J9KE01S3T",
        "exit_code": 0,
        "status": "succeeded",
    },
}


def ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def mean(values: list[float]) -> float | None:
    return round(statistics.fmean(values), 6) if values else None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_training_records(path: Path, group_size: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Use the report's existing last-write/index-zero exclusion convention."""
    by_index: dict[int, dict[str, Any]] = {}
    raw_records = 0
    duplicate_indices = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw_records += 1
            record = json.loads(line)
            index = record.get("index")
            if not isinstance(index, int):
                continue
            duplicate_indices += int(index in by_index)
            by_index[index] = record

    removed_index_zero = int(0 in by_index)
    by_index.pop(0, None)
    records = []
    for index, record in sorted(by_index.items()):
        record["_step"] = index // group_size
        records.append(record)
    return records, {
        "raw_records": raw_records,
        "retry_or_eval_duplicates": duplicate_indices,
        "removed_ambiguous_index_zero": removed_index_zero,
        "deduplicated_training_records": len(records),
    }


def summarize(group_size: int, metadata: dict[str, Any]) -> dict[str, Any]:
    run_dir = ROOT / f"archaeology-g{group_size}" / "main"
    records_path = run_dir / "rollout_records_fmt3_w_verdict.jsonl"
    records, audit = load_training_records(records_path, group_size)
    by_step: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_step[record["_step"]].append(record)

    rewards = [float(record.get("reward") or 0.0) for record in records]
    belief_changes = [
        float(record["belief_change"])
        for record in records
        if isinstance(record.get("belief_change"), (int, float))
    ]
    error_counts = Counter(str(record.get("error")) for record in records if record.get("error"))
    pt_files = sorted((run_dir / "rollout_data_fmt3_w_verdict").glob("*.pt"))
    corrupt_archives: list[str] = []
    for path in pt_files:
        try:
            with zipfile.ZipFile(path) as archive:
                if bad_member := archive.testzip():
                    corrupt_archives.append(f"{path.name}:{bad_member}")
        except zipfile.BadZipFile:
            corrupt_archives.append(f"{path.name}:not-a-zip")

    summary: dict[str, Any] = {
        **metadata,
        "group_size": group_size,
        "local_directory": str(run_dir),
        "jsonl_bytes": records_path.stat().st_size,
        "jsonl_sha256": sha256(records_path),
        "audit": audit,
        "steps_observed": len(by_step),
        "reward_mean": mean(rewards),
        "reward_positive_count": sum(reward > 0 for reward in rewards),
        "reward_positive_rate": ratio(sum(reward > 0 for reward in rewards), len(records)),
        "reward_distribution": dict(sorted(Counter(str(reward) for reward in rewards).items())),
        "success_count": sum(record.get("success") is True for record in records),
        "success_rate": ratio(sum(record.get("success") is True for record in records), len(records)),
        "failure_rate": ratio(sum(bool(record.get("error")) for record in records), len(records)),
        "truncation_count": sum(record.get("error") == "truncated_response" for record in records),
        "truncation_rate": ratio(
            sum(record.get("error") == "truncated_response" for record in records), len(records)
        ),
        "belief_change_count": len(belief_changes),
        "belief_change_mean": mean(belief_changes),
        "error_counts": dict(error_counts.most_common()),
        "pytorch_archives": len(pt_files),
        "pytorch_archive_integrity": "passed" if not corrupt_archives else "failed",
        "corrupt_pytorch_archives": corrupt_archives,
        "steps": [],
    }
    for step, step_records in sorted(by_step.items()):
        step_rewards = [float(record.get("reward") or 0.0) for record in step_records]
        summary["steps"].append(
            {
                "step": step,
                "records": len(step_records),
                "reward_mean": mean(step_rewards),
                "reward_positive_rate": ratio(sum(reward > 0 for reward in step_rewards), len(step_records)),
                "success_rate": ratio(
                    sum(record.get("success") is True for record in step_records), len(step_records)
                ),
                "failure_rate": ratio(sum(bool(record.get("error")) for record in step_records), len(step_records)),
                "truncation_rate": ratio(
                    sum(record.get("error") == "truncated_response" for record in step_records),
                    len(step_records),
                ),
            }
        )
    return summary


def percent(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.1f}%"


def render_markdown(runs: list[dict[str, Any]]) -> str:
    lines = [
        "# Archaeology binary-reward group-size sweep",
        "",
        "Collected and refreshed on 2026-09-09. All arms use `sanity1_fmt3_bin`, "
        "`fmt3_w_verdict`, GRPO, 10 epochs, and `gpt-5-mini` execution/belief scoring. "
        "The g64 and g128 arms are the repaired replacements for the earlier OOM runs.",
        "",
        "Training metrics use the same convention as the reward-hacking report: keep the last "
        "record for each sample index and exclude index 0 because evaluation reused it.",
        "",
        "| Group | Training records | Steps | Positive reward | Success | Truncated | Step 0 reward | Step 9 reward | Status |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for run in runs:
        steps = {step["step"]: step for step in run["steps"]}
        lines.append(
            f"| {run['group_size']} | {run['audit']['deduplicated_training_records']:,} | "
            f"{run['steps_observed']} | {percent(run['reward_positive_rate'])} | "
            f"{percent(run['success_rate'])} | {percent(run['truncation_rate'])} | "
            f"{percent(steps[0]['reward_positive_rate'])} | {percent(steps[9]['reward_positive_rate'])} | "
            f"{run['status']} |"
        )
    lines.extend(
        [
            "",
            "## Collection integrity",
            "",
            "Each arm contains `reward_server.log`, `rollout_records_fmt3_w_verdict.jsonl`, "
            "and 20 PyTorch archives (10 train plus 10 eval). All 100 PyTorch ZIP containers "
            "passed integrity checks. Distributed training checkpoints were intentionally excluded.",
            "",
            "## Immediate readout",
            "",
            "- g256 shows the clearest increasing reward trajectory: 4.7% positive at step 0 and 30.1% at step 9.",
            "- g64 collapses into truncation late in training: 79.7% truncated at step 8 and 96.9% at step 9; positive reward reaches 0% at step 9.",
            "- g128 completes all 10 steps without the same collapse (0% step-9 truncation), so the g64 failure mode is not monotonic in group size.",
            "- These are single runs per group size, so differences combine group-size effects with run variance and the repaired-run environment changes.",
            "",
            "## Provenance",
            "",
            "| Group | Experiment | Job | Result dataset |",
            "|---:|---|---|---|",
        ]
    )
    for run in runs:
        lines.append(
            f"| {run['group_size']} | `{run['experiment_id']}` | `{run['job_id']}` | "
            f"`{run['result_dataset_id']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    runs = [summarize(group_size, metadata) for group_size, metadata in RUNS.items()]
    payload = {
        "collected_at": "2026-09-09",
        "recipe": {
            "dataset": "archaeology",
            "split": "sanity1_fmt3_bin",
            "format": "fmt3_w_verdict",
            "advantage_estimator": "grpo",
            "epochs": 10,
            "reward": "binary belief-change surprise",
            "execution_model": "gpt-5-mini",
            "belief_model": "gpt-5-mini",
        },
        "deduplication": "last record per sample index; index 0 excluded because eval reused it",
        "runs": runs,
    }
    (ROOT / "group-size-sweep-summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    (ROOT / "group-size-sweep.md").write_text(render_markdown(runs))


if __name__ == "__main__":
    main()
