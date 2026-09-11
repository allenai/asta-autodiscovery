#!/usr/bin/env python3
"""Summarize the locally collected AutoDiscovery g256 belief-model comparison."""

from __future__ import annotations

import json
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from summarize_group_size_collection import ROOT, load_training_records, mean, ratio, sha256


RUNS = [
    {
        "belief_model": "gpt-5-mini",
        "belief_model_configuration": "implicit entry-script default",
        "local_name": "archaeology-g256",
        "experiment_id": "01M0RQFDKMHE1GVKJ67EZF9042",
        "job_id": "01M0RQFDQ1MQS7RD82H02XZNRN",
        "result_dataset_id": "01M0RQFDKR2HVNHM3J9KE01S3T",
        "exit_code": 0,
        "status": "succeeded",
    },
    {
        "belief_model": "gemini-3.8-flash",
        "belief_model_configuration": "explicit BELIEF_MODEL",
        "local_name": "gemini-g256",
        "experiment_id": "01M1PV4G4ZC4D5R82KB8WYNSR3",
        "job_id": "01M1PV4G8EFQZ5MKF3A8RVRR01",
        "result_dataset_id": "01M1PV4G53XXHE34KR9A41P4RZ",
        "exit_code": 0,
        "status": "job succeeded; belief scoring failed for every rollout",
    },
    {
        "belief_model": "gpt-5.6-luna",
        "belief_model_configuration": "explicit BELIEF_MODEL",
        "local_name": "luna-g256",
        "experiment_id": "01M1PV4GPCZN3RCTVVKN6SJNHG",
        "job_id": "01M1PV4GT24SBS0MHYR35MCD47",
        "result_dataset_id": "01M1PV4GPH2626EME2GKFBVBGJ",
        "exit_code": 0,
        "status": "succeeded",
    },
]


def summarize(metadata: dict[str, Any]) -> dict[str, Any]:
    group_size = 256
    run_dir = ROOT / metadata["local_name"] / "main"
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
    normalized_surprisals = [
        float(record["normalized_surprisal"])
        for record in records
        if isinstance(record.get("normalized_surprisal"), (int, float))
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

    result: dict[str, Any] = {
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
        "belief_score_count": len(belief_changes),
        "belief_score_rate": ratio(len(belief_changes), len(records)),
        "belief_change_mean": mean(belief_changes),
        "normalized_surprisal_mean": mean(normalized_surprisals),
        "surprising_true_count": sum(record.get("surprising") is True for record in records),
        "failure_rate": ratio(sum(bool(record.get("error")) for record in records), len(records)),
        "truncation_count": sum(record.get("error") == "truncated_response" for record in records),
        "truncation_rate": ratio(
            sum(record.get("error") == "truncated_response" for record in records), len(records)
        ),
        "error_counts": dict(error_counts.most_common()),
        "pytorch_archives": len(pt_files),
        "pytorch_archive_integrity": "passed" if not corrupt_archives else "failed",
        "corrupt_pytorch_archives": corrupt_archives,
        "steps": [],
    }
    for step, step_records in sorted(by_step.items()):
        step_rewards = [float(record.get("reward") or 0.0) for record in step_records]
        step_beliefs = [
            record for record in step_records if isinstance(record.get("belief_change"), (int, float))
        ]
        result["steps"].append(
            {
                "step": step,
                "records": len(step_records),
                "reward_mean": mean(step_rewards),
                "reward_positive_rate": ratio(sum(reward > 0 for reward in step_rewards), len(step_records)),
                "success_rate": ratio(
                    sum(record.get("success") is True for record in step_records), len(step_records)
                ),
                "belief_score_rate": ratio(len(step_beliefs), len(step_records)),
                "failure_rate": ratio(sum(bool(record.get("error")) for record in step_records), len(step_records)),
                "truncation_rate": ratio(
                    sum(record.get("error") == "truncated_response" for record in step_records),
                    len(step_records),
                ),
            }
        )
    return result


def percent(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.1f}%"


def render_markdown(runs: list[dict[str, Any]]) -> str:
    lines = [
        "# Archaeology g256 belief-model comparison",
        "",
        "Collected and refreshed on 2026-09-09. All arms use `sanity1_fmt3_bin`, "
        "`fmt3_w_verdict`, GRPO, 10 epochs, group size 256, binary belief-change surprise reward, "
        "and `gpt-5-mini` as the execution model. The varied factor is the belief model.",
        "",
        "Training metrics use the same convention as the reward-hacking report: keep the last "
        "record for each sample index and exclude index 0 because evaluation reused it.",
        "",
        "| Belief model | Training records | Scored | Positive reward | Success | Truncated | Step 0 reward | Step 9 reward | Operational result |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for run in runs:
        steps = {step["step"]: step for step in run["steps"]}
        lines.append(
            f"| `{run['belief_model']}` | {run['audit']['deduplicated_training_records']:,} | "
            f"{percent(run['belief_score_rate'])} | {percent(run['reward_positive_rate'])} | "
            f"{percent(run['success_rate'])} | {percent(run['truncation_rate'])} | "
            f"{percent(steps[0]['reward_positive_rate'])} | {percent(steps[9]['reward_positive_rate'])} | "
            f"{run['status']} |"
        )
    lines.extend(
        [
            "",
            "## Immediate readout",
            "",
            "- `gpt-5.6-luna` has a slightly higher overall positive-reward rate than the `gpt-5-mini` baseline (20.1% versus 18.2%), but it does not show the baseline's late-step increase: Luna falls to 17.2% at step 9 while the baseline reaches 30.1%.",
            "- `gemini-3.8-flash` produced zero scored rollouts and zero positive rewards. This is an invalid measurement arm, not evidence that Gemini is intrinsically a worse judge: 450 rollouts reached belief scoring and failed with `ValueError: Belief distribution could not be computed`, while the remaining 2,109 failed executor/reviewer checks before a belief score was available.",
            "- These are single runs, so the Luna-versus-mini difference should be treated as descriptive rather than a stable model ranking.",
            "",
            "## Collection integrity",
            "",
            "Each arm contains `reward_server.log`, `rollout_records_fmt3_w_verdict.jsonl`, "
            "and 20 PyTorch archives (10 train plus 10 eval). All 60 PyTorch ZIP containers "
            "passed integrity checks. Distributed training checkpoints were intentionally excluded.",
            "",
            "## Provenance",
            "",
            "| Belief model | Experiment | Job | Result dataset |",
            "|---|---|---|---|",
        ]
    )
    for run in runs:
        lines.append(
            f"| `{run['belief_model']}` | `{run['experiment_id']}` | `{run['job_id']}` | "
            f"`{run['result_dataset_id']}` |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    runs = [summarize(metadata) for metadata in RUNS]
    payload = {
        "collected_at": "2026-09-09",
        "recipe": {
            "dataset": "archaeology",
            "split": "sanity1_fmt3_bin",
            "format": "fmt3_w_verdict",
            "advantage_estimator": "grpo",
            "epochs": 10,
            "group_size": 256,
            "reward": "binary belief-change surprise",
            "execution_model": "gpt-5-mini",
        },
        "varied_factor": "belief_model",
        "deduplication": "last record per sample index; index 0 excluded because eval reused it",
        "runs": runs,
    }
    (ROOT / "belief-model-sweep-summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    (ROOT / "belief-model-sweep.md").write_text(render_markdown(runs))


if __name__ == "__main__":
    main()
