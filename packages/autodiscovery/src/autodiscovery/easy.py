r"""Simplified CLI for AutoDiscovery.

Accepts all user-facing parameters as flat CLI args, builds the metadata
file that the engine expects, and calls ``run.main()`` directly.

Usage::

    uv run --package autodiscovery python -m autodiscovery.easy \
        --name "Plant growth study" \
        --description "Field trial measurements of plant height under varying fertilizer" \
        --intent "Focus on dose-response relationships" \
        --n_experiments 20 \
        --out_dir ./results \
        data/measurements.csv data/treatments.csv

Datasets are positional arguments (file paths).  The wrapper copies them
into a working directory, generates an ``asta``-format ``metadata.json``
next to the copies, and invokes the engine.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from pathlib import Path


def _sniff_columns(path: Path) -> list[dict[str, str]] | None:
    """Read CSV/TSV headers and return column entries with empty descriptions."""
    suffix = path.suffix.lower()
    if suffix not in (".csv", ".tsv"):
        return None
    try:
        with open(path, newline="") as f:
            dialect = csv.Sniffer().sniff(f.read(8192))
            f.seek(0)
            reader = csv.reader(f, dialect)
            headers = next(reader)
        return [{"name": h.strip(), "description": ""} for h in headers if h.strip()]
    except Exception:
        return None


def _build_metadata(
    *,
    name: str,
    description: str,
    domain: str | None,
    intent: str | None,
    dataset_paths: list[Path],
    dataset_descriptions: list[str] | None,
    work_dir: str,
) -> dict:
    """Build an asta-format metadata dict from CLI inputs.

    Dataset names are stored as paths relative to *work_dir* so that
    ``get_datasets_fpaths`` (which joins the metadata directory with the
    name) resolves them correctly.  The caller is responsible for
    symlinking files/directories into *work_dir* so those relative paths
    actually exist.
    """
    datasets = []
    for i, path in enumerate(dataset_paths):
        desc = (
            dataset_descriptions[i]
            if dataset_descriptions and i < len(dataset_descriptions)
            else ""
        )
        if path.is_dir():
            # For directory datasets, walk recursively and add each file
            for child in sorted(path.rglob("*")):
                if child.is_file() and not any(p.startswith(".") for p in child.relative_to(path).parts):
                    rel = str(Path(path.name) / child.relative_to(path))
                    entry: dict = {
                        "name": rel,
                        "description": desc,
                    }
                    columns = _sniff_columns(child)
                    if columns:
                        entry["columns"] = {"raw": columns}
                    datasets.append(entry)
        else:
            entry = {
                "name": path.name,
                "description": desc,
            }
            columns = _sniff_columns(path)
            if columns:
                entry["columns"] = {"raw": columns}
            datasets.append(entry)

    metadata: dict = {
        "description": description,
        "datasets": datasets,
    }
    if domain:
        metadata["domain"] = domain
    if intent:
        metadata["intent"] = intent
    if name:
        metadata["name"] = name
    return metadata


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the simplified CLI."""
    parser = argparse.ArgumentParser(
        prog="auto-discovery",
        description="Simplified AutoDiscovery CLI — flat args, no metadata file required.",
    )

    # -- Datasets (positional) -----------------------------------------------
    parser.add_argument(
        "datasets",
        nargs="+",
        help="Paths to dataset files or directories (CSV, TSV, JSON, etc.)",
    )

    # -- Run info ------------------------------------------------------------
    run = parser.add_argument_group("run info")
    run.add_argument("--name", type=str, default="", help="Short title for the run")
    run.add_argument(
        "--description",
        type=str,
        default="",
        help="Dataset context: provenance, collection method, known gaps",
    )
    run.add_argument("--domain", type=str, help="Research domain (e.g. Genomics)")
    run.add_argument(
        "--intent",
        type=str,
        help="High-level exploration guidance (maps to --user_query in the engine)",
    )
    run.add_argument(
        "--dataset_description",
        type=str,
        action="append",
        dest="dataset_descriptions",
        help="Per-dataset description (repeat once per dataset, in order)",
    )

    # -- Output --------------------------------------------------------------
    out = parser.add_argument_group("output")
    out.add_argument("--out_dir", type=str, required=True, help="Output directory for results")

    # -- Experiment configuration --------------------------------------------
    exp = parser.add_argument_group("experiment configuration")
    exp.add_argument(
        "--n_experiments", type=int, required=True, help="Number of experiments to run"
    )
    exp.add_argument(
        "--exploration_weight",
        type=float,
        default=2.0,
        help="Higher = broader exploration (default: 2.0)",
    )
    exp.add_argument(
        "--surprisal_width",
        type=float,
        default=0.2,
        help="Surprise threshold; lower = more sensitive (default: 0.2)",
    )
    exp.add_argument(
        "--evidence_weight",
        type=float,
        default=2.0,
        help="How much to trust experimental results (default: 2.0)",
    )
    exp.add_argument(
        "--mcts_selection",
        type=str,
        choices=["ucb1", "ucb1_recursive", "pw", "pw_all", "beam_search"],
        default="pw",
        help="MCTS selection strategy (default: pw)",
    )

    # -- Advanced (mirrors ArgParser defaults) -------------------------------
    adv = parser.add_argument_group("advanced")
    adv.add_argument("--model", type=str, default="gemini-3.1-pro-preview")
    adv.add_argument("--belief_model", type=str, default="gemini-3-flash-preview")
    adv.add_argument("--vision_model", type=str, default="gemini-3.1-pro-preview")
    adv.add_argument("--temperature", type=float, default=1.0)
    adv.add_argument("--belief_temperature", type=float, default=1.0)
    adv.add_argument(
        "--reasoning_effort", type=str, choices=["low", "medium", "high"], default="medium"
    )
    adv.add_argument(
        "--belief_reasoning_effort",
        type=str,
        choices=["minimal", "low", "medium", "high"],
        default="low",
    )
    adv.add_argument("--k_experiments", type=int, default=8, help="Branching factor")
    adv.add_argument("--n_warmstart", type=int, default=0)
    adv.add_argument("--batch_size", type=int, default=2)
    adv.add_argument("--n_threads", type=int, default=2)
    adv.add_argument(
        "--belief_mode",
        type=str,
        choices=["boolean", "boolean_cat", "categorical", "categorical_numeric", "gaussian"],
        default="boolean_cat",
    )
    adv.add_argument("--run_eda", action=argparse.BooleanOptionalAction, default=False)
    adv.add_argument("--experiment_first", action=argparse.BooleanOptionalAction, default=False)
    adv.add_argument(
        "--backend",
        type=str,
        choices=["local", "process", "modal"],
        default="process",
    )
    adv.add_argument("--code_timeout", type=int, default=30 * 60)
    adv.add_argument("--n_belief_samples", type=int, default=5)
    adv.add_argument("--kl_scale", type=float, default=5.0)
    adv.add_argument(
        "--reward_mode",
        type=str,
        choices=["belief", "kl", "belief_and_kl"],
        default="belief",
    )

    return parser


def cli_main(argv: list[str] | None = None) -> None:
    """Entry point: parse args, build metadata, and run the engine."""
    parser = build_parser()
    args = parser.parse_args(argv)

    # Resolve dataset paths
    dataset_paths = [Path(p).resolve() for p in args.datasets]
    for p in dataset_paths:
        if not p.exists():
            parser.error(f"Dataset path not found: {p}")

    # Create a working directory with symlinks to datasets + metadata.json.
    # Symlinks let the sandbox (which chdir's to work_dir) find files by
    # relative path without copying potentially large data.
    work_dir = tempfile.mkdtemp(prefix="autodiscovery_work_")
    for p in dataset_paths:
        dst = os.path.join(work_dir, p.name)
        if not os.path.exists(dst):
            os.symlink(str(p), dst)

    metadata = _build_metadata(
        name=args.name,
        description=args.description,
        domain=args.domain,
        intent=args.intent,
        dataset_paths=dataset_paths,
        dataset_descriptions=args.dataset_descriptions,
        work_dir=work_dir,
    )
    metadata_path = os.path.join(work_dir, "metadata.json")
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"Metadata written to {metadata_path}")
    print(f"Working directory: {work_dir}")

    # Build a Namespace that run.main() expects (mirroring ArgParser defaults)
    from argparse import Namespace

    engine_args = Namespace(
        dataset_metadata=metadata_path,
        dataset_metadata_type="asta",
        out_dir=os.path.abspath(args.out_dir),
        work_dir=work_dir,
        n_experiments=args.n_experiments,
        model=args.model,
        belief_model=args.belief_model,
        vision_model=args.vision_model,
        temperature=args.temperature,
        belief_temperature=args.belief_temperature,
        reasoning_effort=args.reasoning_effort,
        belief_reasoning_effort=args.belief_reasoning_effort,
        user_query=args.intent,
        exploration_weight=args.exploration_weight,
        surprisal_width=args.surprisal_width,
        evidence_weight=args.evidence_weight,
        mcts_selection=args.mcts_selection,
        k_experiments=args.k_experiments,
        n_warmstart=args.n_warmstart,
        batch_size=args.batch_size,
        n_threads=args.n_threads,
        belief_mode=args.belief_mode,
        run_eda=args.run_eda,
        experiment_first=args.experiment_first,
        backend=args.backend,
        code_timeout=args.code_timeout,
        n_belief_samples=args.n_belief_samples,
        kl_scale=args.kl_scale,
        reward_mode=args.reward_mode,
        # Defaults for args the easy CLI doesn't expose
        timestamp_dir=False,
        delete_work_dir=True,
        continue_from_dir=None,
        continue_from_json=None,
        only_save_results=False,
        allow_generate_experiments=True,
        k_parents=10,
        implicit_bayes_posterior=False,
        use_binary_reward=False,
        dedupe=False,
        use_online_beliefs=False,
        warmstart_experiments=None,
        bucket_path=None,
        beam_width=8,
        pw_k=1.0,
        pw_alpha=0.5,
        agent_usage_mode="per_response",
    )

    from autodiscovery.run import main

    main(engine_args)

    # Generate static HTML report
    from autodiscovery.report import generate_report

    try:
        report_path = generate_report(os.path.abspath(args.out_dir))
        print(f"\nHTML report: {report_path}")
    except Exception as e:
        print(f"\nWarning: could not generate HTML report: {e}")


if __name__ == "__main__":
    cli_main()
