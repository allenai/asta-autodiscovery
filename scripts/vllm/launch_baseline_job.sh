#!/usr/bin/env bash
#
# Launch AutoDiscovery baseline runs on Beaker with a single API model for ALL
# agents (theorizer = execution, belief = BELIEF_MODEL) — no local vLLM serving.
# Submits one gantry job per dataset.
#
# The in-job wrapper (run_baseline_job.sh) loads base run args from the same
# JSON config as the vLLM path (CONFIG, default scripts/vllm/args.json), dropping
# the vLLM-only key (base_url) and overriding the split models / per-run paths.
# So the baseline shares the config's hyperparameters (selection, belief, ...)
# for a fair comparison against the vLLM/Qwen run.
#
# Usage:
#   # dataset(s) from the config's dataset_metadata:
#   bash scripts/vllm/launch_baseline_job.sh
#   # or override with explicit datasets:
#   bash scripts/vllm/launch_baseline_job.sh <metadata-url> [<metadata-url> ...]
#   DATASETS="a.json b.json" bash scripts/vllm/launch_baseline_job.sh
#
# Config (all overridable via env):
#   WORKSPACE      Beaker workspace     (default: ai2/autodiscovery)
#   CLUSTER        Beaker cluster       (default: ai2/jupiter; Austin cluster for weka)
#   MODEL          single baseline model (theorizer + execution)  (default: gpt-5-mini)
#   BELIEF_MODEL   belief model         (default: = MODEL)
#   N_EXPERIMENTS  MCTS iterations      (default: 10)
#   CONFIG         JSON args file       (default: scripts/vllm/args.json; "" to disable)
#   GPUS           GPUs per job         (default: 0 — baseline needs none)
#   NAME           full run name        (default: baseline-<dataset>-cfg-n<N>)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

WORKSPACE="${WORKSPACE:-ai2/autodiscovery}"
CLUSTER="${CLUSTER:-ai2/jupiter}"
BUDGET="${BUDGET:-ai2/asta}"
MODEL="${MODEL:-gpt-5-mini}"
BELIEF_MODEL="${BELIEF_MODEL:-$MODEL}"
N_EXPERIMENTS="${N_EXPERIMENTS:-10}"
CONFIG="${CONFIG:-$SCRIPT_DIR/args.json}"
GPUS="${GPUS:-0}"

# WEKA-backed output. Requires an Austin cluster that mounts this weka.
WEKA_BUCKET="${WEKA_BUCKET:-nora-default}"
WEKA_MOUNT="${WEKA_MOUNT:-/weka/${WEKA_BUCKET}}"
OUT_DIR="${OUT_DIR:-${WEKA_MOUNT}/sijial/results}"

# Datasets: positional args or DATASETS env, else the config's dataset_metadata.
if [ "$#" -gt 0 ]; then
    datasets=("$@")
elif [ -n "${DATASETS:-}" ]; then
    # shellcheck disable=SC2206
    datasets=(${DATASETS})
elif [ -n "$CONFIG" ] && [ -f "$CONFIG" ]; then
    datasets=("$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("dataset_metadata",""))' "$CONFIG")")
else
    echo "provide dataset metadata as args, via DATASETS, or in the config" >&2
    exit 1
fi

for metadata in "${datasets[@]}"; do
    [ -n "$metadata" ] || { echo "empty dataset entry; skipping" >&2; continue; }
    name="$(basename "$metadata" _metadata.json)"
    # Same convention as the vLLM run (e.g. qwen9b-tcga-breast-cfg-n10):
    # <tag>-<dataset>-cfg-n<N>. Override the whole name via NAME (single dataset).
    dataset_short="$(echo "$name" | sed -e 's/_cancer$//' -e 's/_/-/g')"
    run_name="${NAME:-baseline-${dataset_short}-cfg-n${N_EXPERIMENTS}}"
    echo "Running baseline: $run_name (model=$MODEL, n=$N_EXPERIMENTS)"

    # The in-job wrapper (run_baseline_job.sh) bootstraps uv, builds run args from
    # CONFIG + these env overrides, runs AutoDiscovery, and S3-syncs the results.
    gantry run --allow-dirty --workspace "$WORKSPACE" \
        --cluster "$CLUSTER" \
        --budget "$BUDGET" \
        --no-python \
        --gpus "$GPUS" \
        --weka "${WEKA_BUCKET}:${WEKA_MOUNT}" \
        --priority "${PRIORITY:-normal}" \
        --timeout -1 \
        --task-timeout 24h \
        --env-secret OPENAI_API_KEY=OPENAI_API_KEY \
        --env-secret AWS_ACCESS_KEY_ID=AWS_ACCESS_KEY_ID \
        --env-secret AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY \
        --env "MODEL=$MODEL" \
        --env "BELIEF_MODEL=$BELIEF_MODEL" \
        --env "N_EXPERIMENTS=$N_EXPERIMENTS" \
        --env "OUT_DIR=$OUT_DIR" \
        --env "DATASET_METADATA=$metadata" \
        --env "RUN_NAME=$run_name" \
        --name="$run_name" \
        -- bash scripts/vllm/run_baseline_job.sh
done
