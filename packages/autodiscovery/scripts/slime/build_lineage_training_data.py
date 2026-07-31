#!/usr/bin/env python3
"""Build slime RL training data from AutoDiscovery MCTS node lineages.

Each training sample is one hypothesis-bearing node. Its context is the full
lineage path from the root down to the node's parent — every ancestor
hypothesis, in order — and the target is the node's own hypothesis. Only the
hypotheses (optionally with their Bayesian-surprise scores) are included; no
execution artifacts (code, code output, analysis, or review) ever appear.

Three output formats are produced, all sharing the slime prompt schema
``{"messages": [...], "metadata": {...}}`` (see slime/utils/data.py):

  fmt1  history = ancestor hypotheses only            + open-ended generate prompt
  fmt2  history = (hypothesis, surprise) pairs         + open-ended generate prompt
  fmt3  history = (hypothesis, surprise) pairs         + related generate prompt

Comparing fmt1 -> fmt2 isolates the effect of showing surprise scores;
fmt2 -> fmt3 isolates the effect of the generation prompt. The system prompt and
dataset/context are held identical across all three so those are the only knobs
that vary.

The open-ended and related generate prompts mirror the production on-demand
prompts in ``autodiscovery.mcts.HYPOTHESIS_RELATEDNESS_ONDEMAND`` (open_ended /
related), adapted to reference the lineage shown in context rather than an
inline JSON dump of tried experiments.

Reproducible: deterministic ordering, no randomness, all knobs are CLI flags.

Usage:
    uv run --package asta-autodiscovery python \
        packages/autodiscovery/scripts/slime/build_lineage_training_data.py \
        --input data/nodes_min50_surprise.parquet --out-dir data
"""

from __future__ import annotations

import argparse
import math
import os

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from autodiscovery.run import _theoretical_max_boolean_cat

# --- Prompts -----------------------------------------------------------------

# Neutral theorizer persona, held constant across all three formats so that the
# only differences between formats are the history representation (fmt1 vs
# fmt2/3) and the final generate prompt (fmt1/2 vs fmt3). Mirrors the
# experiment_generator system message in autodiscovery.agents, minus the
# relatedness sentence (which is expressed in the fmt3 generate prompt instead)
# and the fixed hypothesis-count ending.
SYSTEM_PROMPT = (
    "You are a research scientist who is interested in doing open-ended, data-driven "
    "research using the provided dataset(s). Be creative and think of new and interesting "
    "verifiable hypotheses. The hypothesis should be a falsifiable statement that can be "
    "sufficiently tested by an experiment using the provided data. Here are some instructions "
    "that you must follow:\n"
    "1. Strictly use only the dataset(s) provided and do not simulate dummy/synthetic data or "
    "columns that cannot be derived from the existing columns.\n"
    "2. Each hypothesis should be creative, verifiable with a robust statistical test, and "
    "self-contained.\n"
    "3. Use the prior experiments/hypotheses as inspiration, but do not repeat them.\n\n"
    "A good approach: find an interesting context (e.g. a subset defined by categorical "
    "values), interesting variables (including composites derived from existing columns), and "
    "an interesting relationship between them; then make the hypothesis specific — naming the "
    "outcome variable(s), the explanatory variable(s), and the expected direction."
)

# Final generate prompt. fmt1/fmt2 use "open"; fmt3 uses "related". These mirror
# autodiscovery.mcts.HYPOTHESIS_RELATEDNESS_ONDEMAND, adapted so the prior
# experiments are referenced from the context above instead of an inline JSON
# dump. {parent} is the most recent (deepest) ancestor hypothesis.
GENERATE_PROMPT_OPEN = (
    "Given the hypotheses explored above, propose exactly ONE new, falsifiable hypothesis to "
    "test next. Return only the hypothesis statement."
)
GENERATE_PROMPT_RELATED = (
    "Given the hypotheses explored above, propose exactly ONE new, falsifiable hypothesis that "
    "stays closely related to the current line of inquiry (most recent hypothesis: {parent!r}). "
    "It should probe the same phenomenon, variables, or mechanism explored so far — for example "
    "by refining it, extending it to an adjacent context, or testing a plausible causal driver, "
    "moderator, or boundary condition of the observed effect — rather than switching to an "
    "unrelated topic. Do not repeat any hypothesis explored above. Return only the hypothesis "
    "statement."
)
# When a node has no ancestor hypotheses (cold start), there is nothing to relate
# to, so all formats fall back to this neutral prompt.
GENERATE_PROMPT_COLDSTART = (
    "Propose exactly ONE new, falsifiable hypothesis grounded in the dataset(s) described "
    "above. Return only the hypothesis statement."
)

FORMATS = {
    "fmt1_hyps_open": {"scores": False, "prompt": "open"},
    "fmt2_pairs_open": {"scores": True, "prompt": "open"},
    "fmt3_pairs_related": {"scores": True, "prompt": "related"},
    # Like fmt2/fmt3 but each history item is a (hypothesis, surprise, verdict)
    # triplet: verdict is the outcome direction, i.e. which of five buckets the
    # ancestor's posterior belief mean fell into (likely false ... likely true).
    # _w_verdict pairs with open (fmt2) and related (fmt3) generate prompts.
    "fmt2_w_verdict": {"scores": True, "prompt": "open", "verdict": True},
    "fmt3_w_verdict": {"scores": True, "prompt": "related", "verdict": True},
    # fmt1 + verdict: history = (hypothesis, verdict) with no surprise magnitude,
    # open generate prompt. Isolates the verdict (outcome direction) on its own.
    "fmt1_w_verdict": {"scores": False, "prompt": "open", "verdict": True},
}

# Five-bucket verdict on the posterior belief mean in [0, 1]. Encodes the
# *direction* of the surprise (was the hypothesis ultimately supported?) to
# complement the magnitude-only surprise score.
VERDICT_BUCKETS = [
    (0.2, "likely false"),
    (0.4, "maybe false"),
    (0.6, "uncertain"),
    (0.8, "maybe true"),
]

# Columns needed from the node parquet (no execution columns are read).
NODE_COLUMNS = [
    "job_id",
    "node_id",
    "parent_id",
    "level",
    "index",
    "hypothesis",
    "belief_shift_empirical",
    "prior_empirical_mean",
    "posterior_empirical_mean",
    "n_belief_samples",
    "evidence_weight",
    "job_name",
    "job_description",
    "job_domain",
    "job_intent",
    "dataset_names",
    "dataset_descriptions",
]


# --- Helpers -----------------------------------------------------------------


def clean(x) -> str:
    """Normalize a cell to a stripped string, mapping missing/sentinel to ''."""
    if x is None:
        return ""
    if isinstance(x, float) and math.isnan(x):
        return ""
    s = str(x).strip()
    return "" if s.lower() in ("", "n/a", "nan", "none", "null") else s


def as_list(x) -> list[str]:
    """Coerce a cell to a list of clean strings (handles list/ndarray/scalar)."""
    if x is None:
        return []
    if isinstance(x, (list, np.ndarray)):
        return [str(i) for i in x if clean(i)]
    return [str(x)] if clean(x) else []


def abs_normalized_surprisal(row: pd.Series) -> float | None:
    """|normalized_surprisal| = |belief_shift| / theoretical_max, or None.

    Reconstructs the runtime normalized-surprisal magnitude from the flattened
    parquet fields (the raw column is not stored). theoretical_max is the boolean_cat
    maximum mean shift for this node's n_belief_samples and evidence_weight
    (default (0.5, 0.5) Beta prior, matching the belief-class default). This is a
    faithful approximation: because the effective per-node sample count is not
    recoverable, a minority of values can exceed 1.0.
    """
    shift = row["belief_shift_empirical"]
    n = row.get("n_belief_samples")
    w = row.get("evidence_weight")
    if shift is None or (isinstance(shift, float) and math.isnan(shift)):
        return None
    if pd.isna(n) or pd.isna(w):
        return None
    tmax = _theoretical_max_boolean_cat(int(n), float(w))
    if not tmax:
        return None
    return abs(float(shift) / tmax)


def surprise_label(row: pd.Series) -> str:
    """Render a node's raw surprise score (|normalized_surprisal|)."""
    ns = abs_normalized_surprisal(row)
    return f"{ns:.3f}" if ns is not None else "n/a"


def verdict_label(row: pd.Series) -> str:
    """Bucket a node's posterior belief mean into a five-level verdict.

    Encodes the *direction* of the surprise (was the hypothesis ultimately
    supported?), complementing the magnitude-only surprise score. Even bins on
    the posterior mean in [0, 1]: <0.2 likely false ... >=0.8 likely true.
    """
    pm = row.get("posterior_empirical_mean")
    if pm is None or (isinstance(pm, float) and math.isnan(pm)) or pd.isna(pm):
        return "n/a"
    pm = float(pm)
    for hi, label in VERDICT_BUCKETS:
        if pm < hi:
            return label
    return "likely true"


def dataset_context(row: pd.Series) -> str:
    """Study/domain/dataset description block (no execution artifacts)."""
    parts = []
    if clean(row["job_name"]):
        parts.append(f"Study: {clean(row['job_name'])}")
    if clean(row["job_domain"]):
        parts.append(f"Domain: {clean(row['job_domain'])}")
    if clean(row["job_description"]):
        parts.append(f"Description: {clean(row['job_description'])}")
    if clean(row["job_intent"]):
        parts.append(f"Research intent: {clean(row['job_intent'])}")
    header = "\n".join(parts) if parts else "Open-ended data-driven exploration."

    names = as_list(row["dataset_names"])
    descs = as_list(row["dataset_descriptions"])
    if names:
        ds_lines = ["Datasets available:"]
        for i, nm in enumerate(names):
            desc = descs[i] if i < len(descs) else ""
            ds_lines.append(f"\n[{nm}]\n{desc}".rstrip())
        header += "\n\n" + "\n".join(ds_lines)
    return header


def history_block(ancestors: list[pd.Series], with_scores: bool, with_verdict: bool = False) -> str:
    """Render the lineage path (root -> parent) as a numbered hypothesis list.

    Only the hypothesis text is included (fmt1), hypothesis + surprise score
    (fmt2/3), or hypothesis + surprise + verdict triplets (``_w_verdict``). No
    execution artifacts are emitted.
    """
    hyps = [a for a in ancestors if clean(a["hypothesis"])]
    if not hyps:
        return "No hypotheses have been explored along this line of inquiry yet."
    if with_verdict and with_scores:
        suffix = ", each with its measured surprise score and outcome verdict:"
    elif with_verdict:
        suffix = ", each with its outcome verdict:"
    elif with_scores:
        suffix = ", each with its measured surprise score:"
    else:
        suffix = ":"
    lead = "Hypotheses already explored along this line of inquiry (root to current), in order" + suffix
    lines = [lead]
    for i, a in enumerate(hyps, 1):
        lines.append(f"{i}. {clean(a['hypothesis'])}")
        if with_scores:
            lines.append(f"   surprise: {surprise_label(a)}")
        if with_verdict:
            lines.append(f"   verdict: {verdict_label(a)}")
    return "\n".join(lines)


def final_prompt(prompt_kind: str, parent_hypothesis: str, has_history: bool) -> str:
    """Pick the generate prompt for a format, falling back to cold-start."""
    if not has_history:
        return GENERATE_PROMPT_COLDSTART
    if prompt_kind == "related":
        return GENERATE_PROMPT_RELATED.format(parent=parent_hypothesis or "N/A")
    return GENERATE_PROMPT_OPEN


def build_lineage_index(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Per-job node lookup (indexed by node_id) for walking parent chains."""
    return {jid: g.set_index("node_id") for jid, g in df.groupby("job_id")}


def ancestors_root_first(by_job: dict, job_id: str, node_id: str) -> list[pd.Series]:
    """Walk parent_id from the node up to the root; return ancestors root-first.

    Excludes the node itself. Cycle-guarded. A node whose parent is missing from
    the (deduped, filtered) set simply ends the chain — that missing parent is
    the data-loading root, which carries no hypothesis anyway.
    """
    g = by_job[job_id]
    chain: list[pd.Series] = []
    cur = node_id
    seen: set[str] = set()
    while cur in g.index and cur not in seen:
        seen.add(cur)
        row = g.loc[cur]
        if isinstance(row, pd.DataFrame):  # defensive: duplicate node_id
            row = row.iloc[0]
        chain.append(row)
        cur = clean(row["parent_id"])
        if not cur:
            break
    return list(reversed(chain[1:]))  # drop self, order root -> parent


def drop_fully_invalid_runs(df: pd.DataFrame) -> pd.DataFrame:
    """Drop only runs (jobs) that have *no* node with valid prior/posterior means.

    A node is valid when both ``prior_empirical_mean`` and
    ``posterior_empirical_mean`` are present. A run is dropped only when every one
    of its nodes is invalid (the whole run is unscored); any run with at least one
    valid node is kept. Individual invalid nodes are left in place, so their
    surprise score renders as ``n/a`` in lineage history and their metadata score
    is null when they are the target.
    """
    valid = df["prior_empirical_mean"].notna() & df["posterior_empirical_mean"].notna()
    valid_jobs = set(df.loc[valid, "job_id"].unique())
    return df[df["job_id"].isin(valid_jobs)].reset_index(drop=True)


def build_samples(df: pd.DataFrame, fmt_key: str, width: float) -> list[dict]:
    """Build all training samples for one format."""
    spec = FORMATS[fmt_key]
    by_job = build_lineage_index(df)
    samples: list[dict] = []
    for row in df.sort_values(["job_id", "level", "index"]).itertuples(index=False):
        r = pd.Series(row._asdict())
        if int(r["level"]) <= 1 or not clean(r["hypothesis"]):
            continue  # level-1 data-loading roots are not hypotheses
        ancestors = ancestors_root_first(by_job, r["job_id"], r["node_id"])
        hist_hyps = [a for a in ancestors if clean(a["hypothesis"])]
        parent_hyp = clean(hist_hyps[-1]["hypothesis"]) if hist_hyps else ""

        user_content = (
            dataset_context(r)
            + "\n\n"
            + history_block(ancestors, spec["scores"], spec.get("verdict", False))
            + "\n\n"
            + final_prompt(spec["prompt"], parent_hyp, bool(hist_hyps))
        )
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]
        shift = r["belief_shift_empirical"]
        prior = r["prior_empirical_mean"]
        posterior = r["posterior_empirical_mean"]
        abs_ns = abs_normalized_surprisal(r)
        samples.append(
            {
                "messages": messages,
                "metadata": {
                    # slime reward routing + provenance
                    "dataset_id": str(r["job_id"]),
                    "source_name": "autodiscovery",
                    "job_id": str(r["job_id"]),
                    "node_id": str(r["node_id"]),
                    "level": int(r["level"]),
                    "index": int(r["index"]),
                    "n_history": len(hist_hyps),
                    "format": fmt_key,
                    # reference target + labels (for SFT / offline analysis)
                    "target_hypothesis": clean(r["hypothesis"]),
                    # raw surprise score shown in fmt2/fmt3 history lines
                    "abs_normalized_surprisal": abs_ns,
                    "belief_shift": None if pd.isna(shift) else float(shift),
                    "is_surprising": None if pd.isna(shift) else bool(abs(shift) >= width),
                    "prior_mean": None if pd.isna(prior) else float(prior),
                    "posterior_mean": None if pd.isna(posterior) else float(posterior),
                },
            }
        )
    return samples


def write_parquet(samples: list[dict], path: str) -> None:
    """Write samples as parquet with native nested messages/metadata + zstd."""
    table = pa.Table.from_pylist(samples)
    pq.write_table(table, path, compression="zstd")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--input",
        default="data/nodes_min50_surprise.parquet",
        help="Node parquet (flattened mcts nodes). Default: %(default)s",
    )
    parser.add_argument(
        "--out-dir", default="data", help="Directory for the output parquet files. Default: %(default)s"
    )
    parser.add_argument(
        "--prefix", default="lineage_", help="Output filename prefix. Default: %(default)s"
    )
    parser.add_argument(
        "--surprisal-width",
        type=float,
        default=0.2,
        help="|belief_shift| >= width counts as surprising. Default: %(default)s",
    )
    parser.add_argument(
        "--formats",
        default=",".join(FORMATS),
        help="Comma-separated subset of formats to build. Default: all.",
    )
    parser.add_argument(
        "--drop-fully-invalid-runs",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Drop only runs where no node has valid prior/posterior means (the whole "
        "run is unscored); runs with any valid node are kept. Default: on.",
    )
    args = parser.parse_args(argv)

    fmts = [f.strip() for f in args.formats.split(",") if f.strip()]
    unknown = [f for f in fmts if f not in FORMATS]
    if unknown:
        parser.error(f"unknown formats {unknown}; choose from {list(FORMATS)}")

    df = pd.read_parquet(args.input, columns=NODE_COLUMNS)
    before = len(df)
    df = df.drop_duplicates(subset=["job_id", "node_id"], keep="first").reset_index(drop=True)
    print(f"loaded {before:,} node rows -> {len(df):,} after dedup ({df['job_id'].nunique():,} jobs)")

    if args.drop_fully_invalid_runs:
        jobs_before, rows_before = df["job_id"].nunique(), len(df)
        df = drop_fully_invalid_runs(df)
        print(
            f"drop-fully-invalid-runs: kept {df['job_id'].nunique():,} jobs / {len(df):,} nodes "
            f"(dropped {jobs_before - df['job_id'].nunique():,} fully-unscored jobs, "
            f"{rows_before - len(df):,} nodes)"
        )

    os.makedirs(args.out_dir, exist_ok=True)
    for fmt_key in fmts:
        samples = build_samples(df, fmt_key, args.surprisal_width)
        out_path = os.path.join(args.out_dir, f"{args.prefix}{fmt_key}.parquet")
        write_parquet(samples, out_path)
        n_hist = np.array([s["metadata"]["n_history"] for s in samples])
        n_surp = sum(1 for s in samples if s["metadata"]["is_surprising"])
        print(
            f"  {fmt_key:20s} -> {out_path}  "
            f"({len(samples):,} samples, {os.path.getsize(out_path) / 1e6:.1f} MB, "
            f"history: min={n_hist.min()} median={int(np.median(n_hist))} max={n_hist.max()}, "
            f"surprising target={n_surp / len(samples):.1%})"
        )


if __name__ == "__main__":
    main()
