#!/usr/bin/env python3
"""Compare two different reward distributions that are easy to conflate:

  A. the *training data's* reference reward -- metadata.abs_normalized_surprisal
     on the fmt{1,2,3} prompt parquets (what the reference MCTS node earned), and
  B. the *achieved rollout* reward -- what the policy actually earned during the
     Aug 4-5 learning-rate x KL-coefficient sweep, read from the dashboard
     rollout index files.

Usage:
    python plot_reward_data_vs_rollout.py --out-dir .
"""

import argparse
import json
import os

import numpy as np
import pyarrow.parquet as pq
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(REPO, "examples/autodiscovery_rl/data")
ROLLOUT_DIR = os.path.join(REPO, "dashboard-reproduction/public/data/rollouts")

# The Aug 4-5 sweep runs that carry both an LR and a KL in the label and have
# rollout records on disk.
SWEEP = [
    "fmt1-lr5e7-kl001-8x8-ckpt50",
    "fmt1-lr2e6-kl03-4x4-ckpt50",
    "fmt1-lr3e6-kl01-4x4-ckpt50",
    "fmt1-lr4e6-kl01-4x4-ckpt50-r2",
    "fmt2-lr5e6-kl03-4x4-ckpt50",
    "fmt3-lr5e6-kl03-4x4-ckpt50",
    "fmt3-lr3e6-kl03-4x4-ckpt50",
    "fmt1-stable-treatment-lr2e6-kl001",
    "fmt1-stable-treatment-lr5e6-kl03",
]

C_DATA = "#2a78d6"
C_ROLL = "#eb6834"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#d9d8d4"


def training_data_rewards():
    md = pq.read_table(os.path.join(DATA_DIR, "fmt1", "train.parquet"),
                       columns=["metadata"]).column("metadata").to_pylist()
    v = np.array([m["abs_normalized_surprisal"] for m in md], float)
    return v[~np.isnan(v)]


def rollout_rewards():
    catalog = json.load(open(os.path.join(ROLLOUT_DIR, "catalog.json")))
    key_of = {r["label"]: r["key"] for r in catalog["runs"]}
    out = []
    for label in SWEEP:
        p = os.path.join(ROLLOUT_DIR, key_of[label], "index.json")
        if not os.path.exists(p):
            continue
        for e in json.load(open(p))["entries"]:
            if e.get("reason") == "rewarded" and isinstance(e.get("reward"), (int, float)):
                out.append(e["reward"])
    return np.array(out, float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    data = training_data_rewards()
    roll = rollout_rewards()

    fig, ax = plt.subplots(figsize=(9.5, 5.0))
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    bins = np.arange(0.0, 2.45, 0.05)
    ax.hist(data, bins=bins, density=True, color=C_DATA, alpha=0.80,
            label=f"training-data reference reward  (n={data.size:,})", zorder=2)
    ax.hist(roll, bins=bins, density=True, histtype="step", linewidth=2.2,
            color=C_ROLL, label=f"achieved rollout reward, LR×KL sweep  (n={roll.size:,})",
            zorder=3)

    for v, c, name, dy in [(np.median(data), C_DATA, "data", 0.0),
                           (np.median(roll), C_ROLL, "rollout", -0.075)]:
        ax.axvline(v, color=c, linewidth=1.2, linestyle=(0, (4, 3)), zorder=4)
        ax.annotate(f"{name} median {v:.2f}", xy=(v, 0.97 + dy), xycoords=("data", "axes fraction"),
                    xytext=(6, 0), textcoords="offset points",
                    fontsize=9, color=c, ha="left", va="top")

    ax.axvspan(0.18, 0.40, color=INK_2, alpha=0.06, zorder=1)
    ax.annotate("remembered band\n0.2 – 0.3", xy=(0.29, 0.80), xycoords=("data", "axes fraction"),
                fontsize=9, color=INK_2, ha="center", va="center")

    ax.set_xlabel("|normalized surprisal|  (reward)", fontsize=10.5, color=INK)
    ax.set_ylabel("density", fontsize=10.5, color=INK)
    ax.set_xlim(-0.03, 1.9)
    ax.grid(axis="y", color=GRID, linewidth=0.7, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK_2, labelsize=9.5)
    leg = ax.legend(frameon=False, fontsize=9.5, loc="upper right")
    for t in leg.get_texts():
        t.set_color(INK)

    fig.suptitle("Two different reward distributions: the prompts' reference reward vs. what the policy earned",
                 fontsize=12, color=INK, x=0.01, ha="left", y=0.985)
    lo, hi = 0.18, 0.40
    fig.text(0.01, 0.055,
             f"Rollout rewards land on a lattice of ~0.0663 steps: only "
             f"{np.unique(np.round(roll, 4)).size} distinct values in {roll.size:,} rollouts.",
             fontsize=8.5, color=INK_2, ha="left")
    fig.text(0.01, 0.015,
             f"{((roll >= lo) & (roll <= hi)).mean():.0%} of rollout rewards fall in [{lo}, {hi}], "
             f"vs. {((data >= lo) & (data <= hi)).mean():.0%} of the training data's.",
             fontsize=8.5, color=INK_2, ha="left")

    fig.tight_layout(rect=(0, 0.10, 1, 0.945))
    for ext in ("png", "pdf"):
        p = os.path.join(args.out_dir, f"reward_data_vs_rollout.{ext}")
        fig.savefig(p, dpi=200, facecolor=fig.get_facecolor())
        print("wrote", p)

    for name, v in [("training data", data), ("rollout sweep", roll)]:
        print(f"\n{name}: n={v.size:,} mean={v.mean():.4f} median={np.median(v):.4f} "
              f"p25={np.percentile(v, 25):.4f} p75={np.percentile(v, 75):.4f}")


if __name__ == "__main__":
    main()
