#!/usr/bin/env python3
"""Build a durable registry for artifacts from the AutoDiscovery-RL investigation."""

from __future__ import annotations

import hashlib
import html
import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "output" / "autodiscovery-rl-artifact-registry"
COLLECTED = REPO / "logs" / "collected-runs-2026-09-06"
DASHBOARD = REPO / "dashboard-reproduction"
HASH_LIMIT = 8 * 1024 * 1024
SKIP_PARTS = {".git", "node_modules", ".pnpm-store", "__pycache__"}


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def command(*args: str, cwd: Path = REPO) -> str | None:
    try:
        return subprocess.run(args, cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def iter_files(path: Path, *, include_registry: bool = False) -> Iterable[Path]:
    if path.is_file():
        yield path
        return
    if not path.exists():
        return
    for root, dirs, files in os.walk(path):
        dirs[:] = [name for name in dirs if name not in SKIP_PARTS]
        root_path = Path(root)
        for name in files:
            candidate = root_path / name
            if OUT in candidate.parents and not include_registry:
                continue
            yield candidate


def sha256(path: Path) -> str | None:
    if path.stat().st_size > HASH_LIMIT:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def format_bytes(size: int | None) -> str:
    if size is None:
        return "—"
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def path_stats(paths: list[Path]) -> dict[str, Any]:
    include_registry = any(path.resolve() == OUT.resolve() for path in paths)
    files = sorted(
        {
            item.resolve()
            for path in paths
            for item in iter_files(path, include_registry=include_registry)
        }
    )
    existing = [path for path in paths if path.exists()]
    return {
        "exists": len(existing) == len(paths),
        "file_count": len(files),
        "size_bytes": sum(path.stat().st_size for path in files),
        "modified_latest": max(
            (datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat() for path in files),
            default=None,
        ),
    }


def local_href(path: str) -> str:
    return os.path.relpath(REPO / path, OUT).replace(os.sep, "/")


def git_state(path: Path) -> str:
    relative = rel(path)
    status = command("git", "status", "--short", "--untracked-files=all", "--", relative)
    if not status:
        return "tracked-clean" if command("git", "ls-files", "--error-unmatch", relative) else "outside-index"
    states = {line[:2].strip() for line in status.splitlines()}
    if "??" in states:
        return "untracked"
    return "modified"


def classify_file(path: Path) -> str:
    value = rel(path)
    if value.startswith("dashboard-reproduction/"):
        if "/dist/" in f"/{value}":
            return "dashboard-build"
        if "/public/data/" in f"/{value}":
            return "dashboard-data"
        return "dashboard-source"
    if value.startswith("logs/collected-runs"):
        if value.endswith((".md", "summary.json")):
            return "run-analysis"
        return "collected-run-data"
    if value.startswith("logs/fmt"):
        return "legacy-run-data"
    if value.startswith("logs/launch-specs"):
        return "launch-provenance"
    if value.startswith("output/autods-dataset-complexity"):
        return "dataset-complexity"
    if value.startswith("scripts/"):
        return "analysis-source"
    if value.startswith("examples/autodiscovery_rl/reward_data_vs_rollout"):
        return "plot"
    if value.startswith("examples/autodiscovery_rl/plot_reward_data_vs_rollout"):
        return "analysis-source"
    if value.startswith("slime/") or value.startswith("tests/"):
        return "implementation"
    return "standalone-report"


def artifact(
    artifact_id: str,
    title: str,
    category: str,
    kind: str,
    paths: list[str],
    description: str,
    *,
    status: str = "available",
    tags: list[str] | None = None,
    provenance: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    resolved = [REPO / path for path in paths]
    return {
        "id": artifact_id,
        "title": title,
        "category": category,
        "kind": kind,
        "status": status,
        "paths": paths,
        "description": description,
        "tags": tags or [],
        "provenance": provenance or {},
        "notes": notes or [],
        **path_stats(resolved),
    }


def collected_run_artifacts() -> list[dict[str, Any]]:
    group = json.loads((COLLECTED / "group-size-sweep-summary.json").read_text())
    belief = json.loads((COLLECTED / "belief-model-sweep-summary.json").read_text())
    by_name: dict[str, dict[str, Any]] = {}
    for run in group["runs"]:
        name = f"archaeology-g{run['group_size']}"
        by_name[name] = {
            "run": run,
            "tags": ["group-size-sweep", f"g{run['group_size']}", "archaeology"],
        }
    for run in belief["runs"]:
        name = run["local_name"]
        entry = by_name.setdefault(run["local_name"], {"run": run, "tags": []})
        entry["tags"] = sorted(set(entry["tags"] + ["belief-model-sweep", run["belief_model"], "g256"]))
        entry["belief"] = run

    artifacts = []
    for name, entry in sorted(by_name.items()):
        run = entry["run"]
        belief_run = entry.get("belief")
        metrics = belief_run or run
        status = run.get("status", belief_run.get("status") if belief_run else "available")
        artifacts.append(
            artifact(
                f"collected-{name}",
                f"Collected run · {name}",
                "Collected run data",
                "result bundle",
                [f"logs/collected-runs-2026-09-06/{name}"],
                f"Reward log, rollout JSONL, and 10 train + 10 eval tensors. "
                f"Deduplicated training reward-positive rate: {100 * metrics['reward_positive_rate']:.1f}%.",
                status=status,
                tags=entry["tags"],
                provenance={
                    "experiment_id": run["experiment_id"],
                    "job_id": run["job_id"],
                    "result_dataset_id": run["result_dataset_id"],
                    "jsonl_sha256": run["jsonl_sha256"],
                },
            )
        )
    return artifacts


def curated_artifacts() -> list[dict[str, Any]]:
    artifacts = [
        artifact(
            "artifact-registry",
            "AutoDiscovery-RL artifact registry",
            "Registry",
            "HTML + Markdown + JSON",
            [
                "output/autodiscovery-rl-artifact-registry",
                "scripts/build_autodiscovery_rl_artifact_registry.py",
            ],
            "This searchable registry, its concise index, full machine inventory, and reproducible generator.",
            tags=["registry", "provenance"],
            notes=["The registry excludes itself from its recursive file inventory."],
        ),
        artifact(
            "rollout-dashboard",
            "Overall AutoDiscovery RL experiment dashboard",
            "Interactive tools",
            "Sites application",
            ["dashboard-reproduction"],
            "Interactive experiment and rollout browser backed by a 200-run historical catalog and local rollout assets.",
            tags=["dashboard", "rollouts", "experiments", "interactive"],
            provenance={
                "sites_project_id": "appgprj_6a951676a0dc81918e95ce1e3aa19e04",
                "nested_git_head": command("git", "rev-parse", "HEAD", cwd=DASHBOARD),
                "catalog_runs": 200,
                "catalog_runs_with_records": 135,
            },
            notes=["node_modules and nested .git metadata are excluded from size and file inventory."],
        ),
        artifact(
            "rollout-dashboard-catalog",
            "Dashboard experiment catalog and rollout indexes",
            "Interactive tools",
            "JSON data package",
            [
                "dashboard-reproduction/scripts/rollout-runs.json",
                "dashboard-reproduction/public/data/rollouts",
            ],
            "Historical experiment metadata plus generated per-run and per-step rollout indexes used by the dashboard.",
            tags=["catalog", "beaker", "rollout-index"],
        ),
        artifact(
            "reward-hacking-report",
            "Reward hacking and hypothesis repetition investigation",
            "Reports",
            "standalone HTML",
            ["reward-hacking-similarity-investigation.html"],
            "Investigation of reward trajectories, truncation/trace leakage, and semantic repetition across group-size, pseudo-reward, and keyword-reward runs.",
            tags=["reward-hacking", "semantic-similarity", "truncation", "keywords"],
        ),
        artifact(
            "reward-hacking-report-alias",
            "Reward hacking report · underscore filename alias",
            "Reports",
            "duplicate standalone HTML",
            ["reward_hacking_similarity_investigation.html"],
            "Byte-identical alias of the canonical hyphenated reward-hacking report.",
            status="duplicate alias",
            tags=["duplicate", "reward-hacking"],
            notes=["Canonical file: reward-hacking-similarity-investigation.html"],
        ),
        artifact(
            "g256-hypothesis-rollouts",
            "G256 hypothesis rollouts",
            "Reports",
            "standalone HTML",
            ["g256_hypothesis_rollouts.html"],
            "Compact browser for inspecting generated hypotheses from the g256 run.",
            tags=["g256", "hypotheses", "rollouts"],
        ),
        artifact(
            "dataset-complexity-report",
            "AutoDiscovery 29-task dataset complexity analysis",
            "Reports",
            "HTML + CSV + JSON",
            ["output/autods-dataset-complexity-29"],
            "Operational complexity, prompt pressure, statistical risk, schemas, and source-file details for all 29 tasks.",
            tags=["datasets", "complexity", "29-tasks", "scheduling"],
        ),
        artifact(
            "reward-vs-rollout-plot",
            "Reward data versus rollout",
            "Plots",
            "PNG + PDF + source",
            [
                "examples/autodiscovery_rl/reward_data_vs_rollout.png",
                "examples/autodiscovery_rl/reward_data_vs_rollout.pdf",
                "examples/autodiscovery_rl/plot_reward_data_vs_rollout.py",
            ],
            "Static comparison plot and the script that generated it.",
            tags=["reward", "rollout", "plot"],
        ),
        artifact(
            "collected-runs",
            "Collected reward-experiment runs",
            "Collected run data",
            "3.5 GiB result collection",
            ["logs/collected-runs-2026-09-06"],
            "Seven materialized archaeology/group-size/belief-model runs, comparison summaries, diagnostics, and the partial other-28 sweep scaffold.",
            tags=["rollouts", "reward-logs", "pytorch", "beaker-results"],
        ),
        artifact(
            "weka-training-logs",
            "AutoDiscovery-RL training logs on Weka",
            "Collected run data",
            "5.8 GiB Weka collection + transfer manifest",
            [
                "logs/launch-specs/autods-training-logs-to-weka-2026-09-11.md",
                "logs/launch-specs/autods-training-logs-to-weka-2026-09-11.yaml",
            ],
            "Verified 194-file copy of the collected runs and early fmt* bundles on Weka.",
            tags=["weka", "training-logs", "external-storage", "transfer"],
            provenance={
                "experiment_id": "01M291TJTE5N6XWJT3FHZVPF81",
                "job_id": "01M291TJYNFTGMVT0C139BN818",
                "result_dataset_id": "01M291TJTPP7DV7A05WG03WSAJ",
                "staging_dataset_id": "01M290EXVHSY41S4SKBDPZ3VRJ",
                "weka_path": "/weka/nora-default/sijial/training-logs/autodiscovery-rl-2026-09-11",
                "archive_sha256": "cfc59538cb195100244de973ef7e459cb1a3cd9edb6b131193d2e7ee4794ea7b",
            },
            notes=["Weka reports 5.8 GiB; the verified extracted file count is 194."],
        ),
        artifact(
            "group-size-summary",
            "Archaeology binary-reward group-size sweep",
            "Run analyses",
            "Markdown + JSON",
            [
                "logs/collected-runs-2026-09-06/group-size-sweep.md",
                "logs/collected-runs-2026-09-06/group-size-sweep-summary.json",
            ],
            "Comparable g16/g32/g64/g128/g256 reward, success, failure, truncation, and per-step metrics with exact Beaker provenance.",
            tags=["group-size", "g16", "g32", "g64", "g128", "g256"],
        ),
        artifact(
            "belief-model-summary",
            "Archaeology g256 belief-model comparison",
            "Run analyses",
            "Markdown + JSON",
            [
                "logs/collected-runs-2026-09-06/belief-model-sweep.md",
                "logs/collected-runs-2026-09-06/belief-model-sweep-summary.json",
            ],
            "Comparison of gpt-5-mini, gemini-3.8-flash, and gpt-5.6-luna belief scoring at group size 256.",
            tags=["belief-model", "gpt-5-mini", "gemini-3.8-flash", "gpt-5.6-luna"],
        ),
        artifact(
            "g64-diagnostics",
            "Archaeology g64 failure diagnostics",
            "Run analyses",
            "Markdown",
            ["logs/collected-runs-2026-09-06/archaeology-g64/diagnostics.md"],
            "Diagnosis of the false outer failure, Ray completion, reward behavior, and late truncation collapse.",
            tags=["g64", "diagnostics", "reward", "truncation"],
        ),
        artifact(
            "g128-summary",
            "Archaeology g128 run summary",
            "Run analyses",
            "JSON",
            ["logs/collected-runs-2026-09-06/archaeology-g128/summary.json"],
            "Run-level and per-step summary for the repaired g128 archaeology experiment.",
            tags=["g128", "summary"],
        ),
        artifact(
            "other28-scaffold",
            "Other-28 g256 collection scaffold",
            "Collected run data",
            "partial result scaffold",
            ["logs/collected-runs-2026-09-06/other28-g256"],
            "Task directories for the 28-task sweep; only the failed affairs reward log is materialized locally.",
            status="partial: 1 failed, 27 never scheduled",
            tags=["28-tasks", "g256", "partial"],
            provenance={"experiment_id": "01M1PQZF13581SVPXQMP8D2E92"},
        ),
        artifact(
            "legacy-format-results",
            "Early format/reward result bundles",
            "Collected run data",
            "nine result bundles",
            [path.relative_to(REPO).as_posix() for path in sorted((REPO / "logs").glob("fmt*"))],
            "Locally fetched trainer/reward logs for fmt1/fmt2/fmt2v/fmt3/fmt3v belief-change and normalized-surprisal experiments.",
            tags=["format-ablation", "belief-change", "normalized-surprisal"],
        ),
        artifact(
            "group-size-outcomes-tsv",
            "August group-size outcome table",
            "Run analyses",
            "TSV",
            ["logs/results_2026-08-27_28.tsv"],
            "Compact status, duration, reward trajectory, and failure-note table for the initial g32/g64/g128 attempts and restarts.",
            tags=["group-size", "failures", "wandb", "oom"],
        ),
        artifact(
            "complexity4-launch",
            "Four-task complexity-stratified g256 launch",
            "Experiment specifications",
            "Beaker YAML + Markdown manifest",
            [
                "logs/launch-specs/autods-complexity4-g256-gpt5mini-2026-09-09.yaml",
                "logs/launch-specs/autods-complexity4-g256-gpt5mini-2026-09-09.md",
            ],
            "Reproducible launch spec and provenance for boxes, meta-regression-raw, conversation, and nls-raw.",
            status="3 succeeded; boxes failed",
            tags=["launch-spec", "g256", "gpt-5-mini", "four-tasks"],
            provenance={"experiment_id": "01M24Z64AC3CJCKY0522VYWYVP"},
        ),
        artifact(
            "reward-hacking-analysis-source",
            "Reward-hacking analysis and renderer",
            "Analysis source",
            "Python",
            ["scripts/analyze_reward_hacking_runs.py", "scripts/render_reward_hacking_report.py"],
            "Reproducible semantic-similarity analysis and standalone report renderer.",
            tags=["analysis", "rendering", "embeddings"],
        ),
        artifact(
            "dataset-complexity-source",
            "Dataset-complexity analyzer",
            "Analysis source",
            "Python",
            ["scripts/analyze_autods_dataset_complexity.py"],
            "Profiles task data/schema complexity and renders the CSV, JSON, and HTML report package.",
            tags=["analysis", "datasets", "report-generator"],
        ),
        artifact(
            "comparison-summary-source",
            "Group-size and belief-model summary generators",
            "Analysis source",
            "Python",
            ["scripts/summarize_group_size_collection.py", "scripts/summarize_belief_model_collection.py"],
            "Regenerates comparison metrics, hashes, integrity checks, and Markdown reports from collected runs.",
            tags=["analysis", "group-size", "belief-model", "integrity"],
        ),
        artifact(
            "truncation-penalty-implementation",
            "Keyword reward truncation penalty",
            "Implementation changes",
            "Python source + test",
            ["slime/rollout/rm_hub/keyword.py", "tests/test_autodiscovery_reward_shaping.py"],
            "Applies AUTODISCOVERY_FAILURE_REWARD to truncated keyword-reward samples and verifies a truncated match receives -1 when configured.",
            status="working-tree modification",
            tags=["length-penalty", "truncation", "keyword-reward", "test"],
        ),
    ]
    artifacts.extend(collected_run_artifacts())

    legacy_ids = {
        "fmt1-ns2": "01KYT4HKCRC0RZ39MEVA9AS9XC",
        "fmt2-bc2": "01KYT4JSHT3594RTJPP5DR7EKC",
        "fmt2-ns2": "01KYT4KHSGX4YKDXBKKRKBRKSW",
        "fmt2v-bc2": "01KYT4MRM2E0JXV8JSANJ80J7C",
        "fmt2v-ns3": "01KYTC9QHSVYC9NA61MBC78CMP",
        "fmt3-bc2": "01KYT4K8Z2ZC626SSTVAVR3X5P",
        "fmt3-ns2": "01KYT4JA1D0K38CHGWHCQG4KGC",
        "fmt3v-bc2": "01KYT4KHKY5S5QB12ANE1XQQ9S",
        "fmt3v-ns2": "01KYT4KWY9Y3PGBVNHB09HKX6A",
    }
    for name, dataset_id in legacy_ids.items():
        path = REPO / "logs" / name
        artifacts.append(
            artifact(
                f"legacy-{name}",
                f"Early result bundle · {name}",
                "Collected run data",
                "trainer/reward logs",
                [f"logs/{name}"],
                "Fetched early format/reward experiment output.",
                status="partial" if name == "fmt2v-ns3" else "available",
                tags=["legacy", name.split("-")[0], name.split("-")[1]],
                provenance={"result_dataset_id": dataset_id},
            )
        )
    return artifacts


def recent_experiments() -> list[dict[str, Any]]:
    group_names = {
        "01M0RQFD4QVN3BS85PYDPC0MNX": "autods-sanity1-fmt3-binrw-mainharness-g16-v4",
        "01M115W5YND6WFMHTW59SAMTER": "autods-sanity1-fmt3-binrw-mainharness-g32-24h",
        "01M1PQYZA5BMGHEZJKBDXRZEGC": "autods-sanity1-fmt3-binrw-mainharness-g64-gpt5mini-minrt1h-v11",
        "01M1V3C7AC1B14HS4NB33Y4Y0J": "autods-sanity1-fmt3-binrw-mainharness-g128-gpt5mini-minrt1h-v12",
        "01M0RQFDKMHE1GVKJ67EZF9042": "autods-sanity1-fmt3-binrw-mainharness-g256-v4",
    }
    belief_names = {
        "01M1PV4G4ZC4D5R82KB8WYNSR3": "autods-sanity1-fmt3-binrw-mainharness-g256-gemini38-minrt1h-wandbfix-v3",
        "01M1PV4GPCZN3RCTVVKN6SJNHG": "autods-sanity1-fmt3-binrw-mainharness-g256-gpt56luna-minrt1h-wandbfix-v3",
    }
    merged: dict[str, dict[str, Any]] = {}
    group = json.loads((COLLECTED / "group-size-sweep-summary.json").read_text())
    for run in group["runs"]:
        merged[run["experiment_id"]] = {
            "id": run["experiment_id"],
            "name": group_names[run["experiment_id"]],
            "status": run["status"],
            "exit_code": run["exit_code"],
            "family": "group-size",
            "created": None,
            "result_dataset_ids": [run["result_dataset_id"]],
            "local_paths": [rel(COLLECTED / f"archaeology-g{run['group_size']}")],
            "source": "refreshed local summary",
            "beaker_url": f"https://beaker.org/ex/{run['experiment_id']}",
        }
    belief = json.loads((COLLECTED / "belief-model-sweep-summary.json").read_text())
    for run in belief["runs"]:
        if run["experiment_id"] in merged:
            merged[run["experiment_id"]]["family"] = "group-size + belief-model"
            continue
        merged[run["experiment_id"]] = {
            "id": run["experiment_id"],
            "name": belief_names[run["experiment_id"]],
            "status": run["status"],
            "exit_code": run["exit_code"],
            "family": "belief-model",
            "created": None,
            "result_dataset_ids": [run["result_dataset_id"]],
            "local_paths": [rel(COLLECTED / run["local_name"])],
            "source": "refreshed local summary",
            "beaker_url": f"https://beaker.org/ex/{run['experiment_id']}",
        }

    merged["01M1PQZF13581SVPXQMP8D2E92"] = {
        "id": "01M1PQZF13581SVPXQMP8D2E92",
        "name": "autods-task1-other28-g256-10ep-gpt5mini-minrt1h-v2",
        "status": "1 failed; 27 created/unscheduled",
        "exit_code": None,
        "family": "multi-task",
        "created": "2026-09-04T17:38:02.914991Z",
        "result_dataset_ids": ["01M1PQZF1EGHWMX4DNDSYS119H"],
        "local_paths": ["logs/collected-runs-2026-09-06/other28-g256"],
        "source": "Beaker status refreshed 2026-09-11",
        "beaker_url": "https://beaker.org/ex/01M1PQZF13581SVPXQMP8D2E92",
        "jobs_summary": {"failed": 1, "created": 27},
    }
    merged["01M24Z64AC3CJCKY0522VYWYVP"] = {
        "id": "01M24Z64AC3CJCKY0522VYWYVP",
        "name": "autods-complexity4-g256-gpt5mini-minrt1h-v1",
        "status": "3 succeeded; 1 failed",
        "exit_code": None,
        "family": "complexity-stratified tasks",
        "created": "2026-09-10T06:13:23.40411Z",
        "result_dataset_ids": [
            "01M24Z64AT0EZ5KZ264EVVY1P1",
            "01M24Z64ED4AER07QVVXFSRBW5",
            "01M24Z64P6FANFFRNR31PQ9E34",
            "01M24Z64SQF6ZV4Y8KSS07S8F3",
        ],
        "local_paths": ["logs/launch-specs/autods-complexity4-g256-gpt5mini-2026-09-09.md"],
        "source": "Beaker status refreshed 2026-09-11",
        "beaker_url": "https://beaker.org/ex/01M24Z64AC3CJCKY0522VYWYVP",
        "jobs": [
            {"name": "boxes", "job_id": "01M24Z64E6SZX4N3P0EN52RAXE", "status": "failed", "exit_code": 1, "result_dataset_id": "01M24Z64AT0EZ5KZ264EVVY1P1"},
            {"name": "meta-regression-raw", "job_id": "01M24Z64P1APEZS84JM2QFPYV3", "status": "succeeded", "exit_code": 0, "result_dataset_id": "01M24Z64ED4AER07QVVXFSRBW5"},
            {"name": "conversation", "job_id": "01M24Z64SJ5BMQ4EHC9HM0BC2A", "status": "succeeded", "exit_code": 0, "result_dataset_id": "01M24Z64P6FANFFRNR31PQ9E34"},
            {"name": "nls-raw", "job_id": "01M24Z64X6DVZQC3CSF5VRWYJ9", "status": "succeeded", "exit_code": 0, "result_dataset_id": "01M24Z64SQF6ZV4Y8KSS07S8F3"},
        ],
    }
    return list(merged.values())


def external_experiments() -> list[dict[str, Any]]:
    historical_path = DASHBOARD / "scripts" / "rollout-runs.json"
    historical = json.loads(historical_path.read_text())["runs"]
    merged: dict[str, dict[str, Any]] = {}
    for run in historical:
        experiment_id = run.get("experimentId")
        if not experiment_id:
            continue
        merged[experiment_id] = {
            "id": experiment_id,
            "name": run.get("name"),
            "status": run.get("status"),
            "exit_code": run.get("exitCode"),
            "family": run.get("family"),
            "created": run.get("created"),
            "result_dataset_ids": [run["datasetId"]] if run.get("datasetId") else [],
            "local_paths": [run["localPath"]] if run.get("localPath") else [],
            "has_records": run.get("hasRecords"),
            "source": "dashboard historical snapshot through 2026-08-31",
            "beaker_url": run.get("beaker") or f"https://beaker.org/ex/{experiment_id}",
        }
    for run in recent_experiments():
        if run["id"] in merged:
            previous = merged[run["id"]]
            previous.update({key: value for key, value in run.items() if value is not None})
            previous["source"] = "dashboard snapshot + refreshed local summary"
        else:
            merged[run["id"]] = run
    return sorted(merged.values(), key=lambda run: (run.get("created") or "", run["id"]), reverse=True)


def file_inventory() -> list[dict[str, Any]]:
    roots = [
        REPO / "logs",
        REPO / "output" / "autods-dataset-complexity-29",
        DASHBOARD,
        REPO / "g256_hypothesis_rollouts.html",
        REPO / "reward-hacking-similarity-investigation.html",
        REPO / "reward_hacking_similarity_investigation.html",
        REPO / "examples" / "autodiscovery_rl" / "plot_reward_data_vs_rollout.py",
        REPO / "examples" / "autodiscovery_rl" / "reward_data_vs_rollout.png",
        REPO / "examples" / "autodiscovery_rl" / "reward_data_vs_rollout.pdf",
        REPO / "scripts" / "analyze_reward_hacking_runs.py",
        REPO / "scripts" / "render_reward_hacking_report.py",
        REPO / "scripts" / "analyze_autods_dataset_complexity.py",
        REPO / "scripts" / "summarize_group_size_collection.py",
        REPO / "scripts" / "summarize_belief_model_collection.py",
        REPO / "scripts" / "build_autodiscovery_rl_artifact_registry.py",
        REPO / "slime" / "rollout" / "rm_hub" / "keyword.py",
        REPO / "tests" / "test_autodiscovery_reward_shaping.py",
    ]
    paths = sorted({path.resolve() for root in roots for path in iter_files(root)})
    inventory = []
    for path in paths:
        stat = path.stat()
        inventory.append(
            {
                "path": rel(path),
                "category": classify_file(path),
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
                "sha256": sha256(path),
                "git_state": git_state(path),
            }
        )
    return inventory


def markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# AutoDiscovery-RL artifact registry",
        "",
        f"Generated {payload['generated_at']}. This registry covers {summary['curated_artifacts']} curated artifacts, "
        f"{summary['inventory_files']} underlying local files ({format_bytes(summary['inventory_bytes'])}), "
        f"and {summary['external_experiments']} Beaker experiments.",
        "",
        "Open the [searchable HTML registry](artifact-registry.html) or use "
        "[`artifact-registry.json`](artifact-registry.json) for the full file- and experiment-level inventory.",
        "",
        "## Primary artifacts",
        "",
        "| Category | Artifact | Kind | Status | Size | Local path |",
        "|---|---|---|---|---:|---|",
    ]
    for item in sorted(payload["artifacts"], key=lambda value: (value["category"], value["title"])):
        paths = "<br>".join(f"[`{path}`](../../{path})" for path in item["paths"][:3])
        if len(item["paths"]) > 3:
            paths += f"<br>+{len(item['paths']) - 3} more"
        lines.append(
            f"| {item['category']} | {item['title']} | {item['kind']} | {item['status']} | "
            f"{format_bytes(item['size_bytes'])} | {paths} |"
        )
    lines.extend(
        [
            "",
            "## External experiment coverage",
            "",
            f"- Historical dashboard snapshot: {summary['historical_dashboard_experiments']} experiments through 2026-08-31.",
            f"- Unique experiments after merging refreshed September runs: {summary['external_experiments']}.",
            f"- Unique referenced Beaker result datasets: {summary['result_datasets']}.",
            "- September status was refreshed for the group-size, belief-model, other-28, and four-task complexity experiments. Historical dashboard statuses are retained as snapshots, not claimed as live.",
            "",
            "## Scope",
            "",
            "Included: generated reports, charts, dashboard source/build/data, collected logs and rollout tensors, Weka transfer provenance, launch specs, analysis scripts, and the keyword truncation-penalty working-tree change and test.",
            "",
            "Excluded: third-party dependency caches (`node_modules`, `.pnpm-store`), Git internals, Python bytecode, base repository files not created or changed during the investigation, and unrelated `output/pdf` and `tmp/pdfs` artifacts.",
            "",
        ]
    )
    return "\n".join(lines)


def render_artifact_row(item: dict[str, Any]) -> str:
    path_links = "<br>".join(
        f'<a href="{html.escape(local_href(path))}"><code>{html.escape(path)}</code></a>'
        for path in item["paths"][:3]
    )
    if len(item["paths"]) > 3:
        path_links += f"<br><span class=muted>+{len(item['paths']) - 3} more paths</span>"
    provenance = []
    for key in ("experiment_id", "job_id", "result_dataset_id", "sites_project_id"):
        if value := item["provenance"].get(key):
            if key == "experiment_id":
                provenance.append(f'<a href="https://beaker.org/ex/{html.escape(str(value))}">{html.escape(str(value))}</a>')
            else:
                provenance.append(f"{html.escape(key)}: <code>{html.escape(str(value))}</code>")
    search = " ".join(
        [item["title"], item["category"], item["kind"], item["status"], item["description"], *item["tags"], *item["paths"]]
    ).lower()
    tags = " ".join(f"<span class=tag>{html.escape(tag)}</span>" for tag in item["tags"][:6])
    return f"""
      <tr data-search="{html.escape(search)}" data-category="{html.escape(item['category'])}">
        <td><span class=artifact-title>{html.escape(item['title'])}</span><div>{tags}</div></td>
        <td>{html.escape(item['category'])}<br><span class=muted>{html.escape(item['kind'])}</span></td>
        <td><span class=status>{html.escape(item['status'])}</span></td>
        <td>{html.escape(item['description'])}</td>
        <td>{path_links}</td>
        <td class=num>{format_bytes(item['size_bytes'])}<br><span class=muted>{item['file_count']} files</span></td>
        <td>{'<br>'.join(provenance) or '—'}</td>
      </tr>"""


def render_experiment_row(run: dict[str, Any]) -> str:
    datasets = "<br>".join(f"<code>{html.escape(value)}</code>" for value in run.get("result_dataset_ids", [])[:4]) or "—"
    if len(run.get("result_dataset_ids", [])) > 4:
        datasets += f"<br><span class=muted>+{len(run['result_dataset_ids']) - 4} more</span>"
    search = " ".join(str(run.get(key) or "") for key in ("id", "name", "status", "family", "source")).lower()
    return f"""
      <tr data-exp-search="{html.escape(search)}" data-family="{html.escape(str(run.get('family') or 'uncategorized'))}">
        <td><a href="{html.escape(run['beaker_url'])}"><code>{html.escape(run['id'])}</code></a></td>
        <td>{html.escape(run.get('name') or '—')}</td>
        <td>{html.escape(run.get('family') or '—')}</td>
        <td><span class=status>{html.escape(str(run.get('status') or '—'))}</span></td>
        <td>{html.escape(str(run.get('exit_code'))) if run.get('exit_code') is not None else '—'}</td>
        <td>{datasets}</td>
        <td><span class=muted>{html.escape(run.get('source') or '—')}</span></td>
      </tr>"""


def render_file_row(item: dict[str, Any]) -> str:
    search = f"{item['path']} {item['category']} {item['git_state']}".lower()
    digest = item["sha256"][:12] if item["sha256"] else "—"
    return f"""
      <tr data-file-search="{html.escape(search)}" data-file-category="{html.escape(item['category'])}">
        <td><a href="{html.escape(local_href(item['path']))}"><code>{html.escape(item['path'])}</code></a></td>
        <td>{html.escape(item['category'])}</td>
        <td>{html.escape(item['git_state'])}</td>
        <td class=num>{format_bytes(item['size_bytes'])}</td>
        <td><code>{digest}</code></td>
        <td><span class=muted>{html.escape(item['modified'])}</span></td>
      </tr>"""


def html_page(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    artifact_rows = "".join(render_artifact_row(item) for item in sorted(payload["artifacts"], key=lambda x: (x["category"], x["title"])))
    experiment_rows = "".join(render_experiment_row(run) for run in payload["external_experiments"])
    file_rows = "".join(render_file_row(item) for item in payload["files"])
    artifact_categories = sorted({item["category"] for item in payload["artifacts"]})
    experiment_families = sorted({str(item.get("family") or "uncategorized") for item in payload["external_experiments"]})
    file_categories = sorted({item["category"] for item in payload["files"]})
    options = lambda values: "".join(f'<option value="{html.escape(value)}">{html.escape(value)}</option>' for value in values)
    duplicate_groups = payload["duplicate_files"]
    duplicates_html = "".join(
        f"<li><code>{html.escape(group['sha256'][:16])}</code>: " + ", ".join(
            f'<a href="{html.escape(local_href(path))}"><code>{html.escape(path)}</code></a>' for path in group["paths"]
        ) + "</li>"
        for group in duplicate_groups
    ) or "<li>No hashed duplicate files detected.</li>"
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AutoDiscovery-RL artifact registry</title>
<style>
:root{{--ink:#17202c;--muted:#657184;--line:#d9dee7;--panel:#fff;--bg:#f3f5f8;--accent:#315f9b;--soft:#e9f0fa}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 ui-sans-serif,system-ui,-apple-system,sans-serif}}
main{{max-width:1500px;margin:auto;padding:28px}} h1{{margin:0 0 4px;font-size:30px}} h2{{margin:28px 0 10px;font-size:20px}} p{{max-width:1000px}}
.muted{{color:var(--muted);font-size:12px}} .cards{{display:grid;grid-template-columns:repeat(4,minmax(160px,1fr));gap:12px;margin:20px 0}}
.card,.panel{{background:var(--panel);border:1px solid var(--line);border-radius:10px}} .card{{padding:16px}} .card strong{{display:block;font-size:26px;color:var(--accent)}}
.panel{{padding:16px;margin:12px 0}} .controls{{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}}
input,select{{padding:9px 11px;border:1px solid var(--line);border-radius:7px;background:#fff;font:inherit}} input{{min-width:330px;flex:1}}
.table-wrap{{overflow:auto;border:1px solid var(--line);border-radius:8px}} table{{border-collapse:collapse;width:100%;background:#fff}}
th{{position:sticky;top:0;background:#26364f;color:#fff;text-align:left;padding:9px 8px;white-space:nowrap;font-size:11px;letter-spacing:.03em}}
td{{padding:9px 8px;border-bottom:1px solid #e8ebf0;vertical-align:top}} tr:hover{{background:#f7faff}} td.num{{text-align:right;white-space:nowrap}}
code{{font:11px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace}} a{{color:#245c9b;text-decoration:none}} a:hover{{text-decoration:underline}}
.artifact-title{{font-weight:700;display:block;margin-bottom:4px}} .tag,.status{{display:inline-block;border-radius:999px;padding:2px 7px;font-size:10px;margin:1px 2px 1px 0}}
.tag{{background:#edf0f4;color:#506078}} .status{{background:var(--soft);color:#274f81}} details{{margin-top:12px}} .hidden{{display:none}}
@media(max-width:800px){{main{{padding:16px}}.cards{{grid-template-columns:repeat(2,1fr)}}input{{min-width:100%}}}}
</style></head><body><main>
<h1>AutoDiscovery-RL artifact registry</h1>
<p class=muted>Generated {html.escape(payload['generated_at'])} · workspace <code>{html.escape(str(REPO))}</code></p>
<p>A durable index of the reports, interactive tools, collected run data, experiment specifications, analysis code, and remote Beaker provenance created during the AutoDiscovery-RL investigation.</p>
<div class=cards>
  <div class=card><strong>{summary['curated_artifacts']}</strong><span>curated artifacts</span></div>
  <div class=card><strong>{summary['inventory_files']}</strong><span>underlying local files</span></div>
  <div class=card><strong>{format_bytes(summary['inventory_bytes'])}</strong><span>inventoried storage</span></div>
  <div class=card><strong>{summary['external_experiments']}</strong><span>Beaker experiments</span></div>
</div>
<section class=panel><strong>Scope.</strong> Generated reports/charts, dashboard source/build/data, logs/rollout tensors, Weka transfer provenance, launch specs, analysis scripts, and the keyword truncation-penalty change are included. The bulk logs are stored at <code>/weka/nora-default/sijial/training-logs/autodiscovery-rl-2026-09-11</code>. Dependency caches, Git internals, bytecode, untouched base-repository files, and unrelated PDF work are excluded.</section>

<h2>Curated artifacts <span class=muted id=artifact-count></span></h2>
<div class=controls><input id=artifact-search placeholder="Search artifacts, tags, paths, experiment IDs…"><select id=artifact-category><option value="">All categories</option>{options(artifact_categories)}</select></div>
<div class=table-wrap><table><thead><tr><th>Artifact</th><th>Category / kind</th><th>Status</th><th>Description</th><th>Local path</th><th>Size</th><th>Provenance</th></tr></thead><tbody id=artifacts>{artifact_rows}</tbody></table></div>

<h2>Beaker experiments <span class=muted id=experiment-count></span></h2>
<p class=muted>The 200-run dashboard statuses are a historical snapshot through 2026-08-31. September group-size, belief-model, other-28, and four-task experiment statuses were refreshed on 2026-09-11.</p>
<div class=controls><input id=experiment-search placeholder="Search experiment name, ID, status, family…"><select id=experiment-family><option value="">All families</option>{options(experiment_families)}</select></div>
<div class=table-wrap><table><thead><tr><th>Experiment</th><th>Name</th><th>Family</th><th>Status</th><th>Exit</th><th>Result dataset(s)</th><th>Freshness</th></tr></thead><tbody id=experiments>{experiment_rows}</tbody></table></div>

<details class=panel><summary><strong>File-level inventory</strong> · {summary['inventory_files']} files <span class=muted id=file-count></span></summary>
<div class=controls><input id=file-search placeholder="Search paths, type, or Git state…"><select id=file-category><option value="">All file types</option>{options(file_categories)}</select></div>
<div class=table-wrap><table><thead><tr><th>Path</th><th>Type</th><th>Git state</th><th>Size</th><th>SHA-256 prefix</th><th>Modified</th></tr></thead><tbody id=files>{file_rows}</tbody></table></div></details>

<details class=panel><summary><strong>Duplicate files detected by SHA-256</strong> · {len(duplicate_groups)} groups</summary><ul>{duplicates_html}</ul></details>
<p class=muted>Machine-readable registry: <a href="artifact-registry.json"><code>artifact-registry.json</code></a> · concise index: <a href="README.md"><code>README.md</code></a></p>
<script>
function filterRows(bodyId, searchId, selectId, searchAttr, categoryAttr, countId) {{
  const rows=[...document.querySelectorAll(`#${{bodyId}} tr`)];
  const run=()=>{{const q=document.getElementById(searchId).value.toLowerCase().trim();const c=document.getElementById(selectId).value;let shown=0;for(const row of rows){{const ok=(!q||row.dataset[searchAttr].includes(q))&&(!c||row.dataset[categoryAttr]===c);row.classList.toggle('hidden',!ok);shown+=ok?1:0}}document.getElementById(countId).textContent=`· ${{shown}} / ${{rows.length}} shown`;}};
  document.getElementById(searchId).addEventListener('input',run);document.getElementById(selectId).addEventListener('change',run);run();
}}
filterRows('artifacts','artifact-search','artifact-category','search','category','artifact-count');
filterRows('experiments','experiment-search','experiment-family','expSearch','family','experiment-count');
filterRows('files','file-search','file-category','fileSearch','fileCategory','file-count');
</script></main></body></html>"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    artifacts = curated_artifacts()
    files = file_inventory()
    experiments = external_experiments()
    hashes: dict[str, list[str]] = defaultdict(list)
    for item in files:
        if item["sha256"]:
            hashes[item["sha256"]].append(item["path"])
    duplicates = [
        {"sha256": digest, "paths": paths}
        for digest, paths in sorted(hashes.items())
        if len(paths) > 1
    ]
    result_datasets = {
        dataset_id
        for run in experiments
        for dataset_id in run.get("result_dataset_ids", [])
        if dataset_id
    }
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(),
        "workspace": str(REPO),
        "scope": {
            "included": [
                "AutoDiscovery-RL generated reports and plots",
                "rollout dashboard source, build, and data",
                "collected result logs, JSONL records, and PyTorch rollout archives",
                "launch specifications and analysis scripts",
                "keyword truncation-penalty implementation and test",
                "historical and refreshed Beaker experiment/result-dataset provenance",
                "verified Weka mirror at /weka/nora-default/sijial/training-logs/autodiscovery-rl-2026-09-11",
            ],
            "excluded": [
                "node_modules and .pnpm-store dependency caches",
                "Git internals and Python bytecode",
                "untouched base-repository files",
                "unrelated output/pdf and tmp/pdfs work",
            ],
        },
        "repository": {
            "head": command("git", "rev-parse", "HEAD"),
            "branch": command("git", "branch", "--show-current"),
            "dashboard_head": command("git", "rev-parse", "HEAD", cwd=DASHBOARD),
            "sites_project_id": "appgprj_6a951676a0dc81918e95ce1e3aa19e04",
        },
        "summary": {
            "curated_artifacts": len(artifacts),
            "inventory_files": len(files),
            "inventory_bytes": sum(item["size_bytes"] for item in files),
            "external_experiments": len(experiments),
            "historical_dashboard_experiments": 200,
            "result_datasets": len(result_datasets),
            "artifact_categories": dict(Counter(item["category"] for item in artifacts)),
            "file_categories": dict(Counter(item["category"] for item in files)),
            "experiment_families": dict(Counter(str(item.get("family") or "uncategorized") for item in experiments)),
        },
        "artifacts": artifacts,
        "external_experiments": experiments,
        "result_dataset_ids": sorted(result_datasets),
        "duplicate_files": duplicates,
        "files": files,
    }
    (OUT / "artifact-registry.json").write_text(json.dumps(payload, indent=2) + "\n")
    (OUT / "README.md").write_text(markdown(payload))
    (OUT / "artifact-registry.html").write_text(html_page(payload))
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
