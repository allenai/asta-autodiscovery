#!/usr/bin/env bash
#
# Launch AutoDiscovery baseline runs on Beaker with a single API model for ALL
# agents (theorizer = execution = belief) — no local vLLM serving. Submits one
# gantry job per dataset.
#
# Base run args are loaded from the same JSON config as the vLLM path
# (CONFIG, default scripts/vllm/args.json), EXCEPT the keys that only make sense
# with a served theorizer (base_url, theorizer_model/execution_model) and the
# per-run paths — those are set by this script. So the baseline shares the
# config's hyperparameters (dataset, selection, belief settings, ...) for a fair
# comparison against the vLLM/Qwen run.
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
#   CLUSTER        Beaker cluster       (default: ai2/jupiter; must be an Austin
#                  cluster for the weka out_dir)
#   MODEL          single baseline model (theorizer + execution)  (default: gpt-5-mini)
#   BELIEF_MODEL   belief model         (default: = MODEL)
#   N_EXPERIMENTS  MCTS iterations      (default: 10)
#   CONFIG         JSON args file       (default: scripts/vllm/args.json; "" to disable)
#   GPUS           GPUs per job         (default: 0 — baseline needs none)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

WORKSPACE="${WORKSPACE:-ai2/autodiscovery}"
CLUSTER="${CLUSTER:-ai2/jupiter}"
BUDGET="${BUDGET:-ai2/asta}"
MODEL="${MODEL:-gpt-5-mini}"
BELIEF_MODEL="${BELIEF_MODEL:-$MODEL}"
N_EXPERIMENTS="${N_EXPERIMENTS:-10}"
CONFIG="${CONFIG:-$SCRIPT_DIR/args.json}"
GPUS="${GPUS:-0}"
# uv monorepo: skip gantry's pip build (--no-python) and run via uv.
RUN_CMD="${RUN_CMD:-uv run --package asta-autodiscovery python -m autodiscovery.run}"

# WEKA-backed output. Requires an Austin cluster that mounts this weka.
WEKA_BUCKET="${WEKA_BUCKET:-nora-default}"
WEKA_MOUNT="${WEKA_MOUNT:-/weka/${WEKA_BUCKET}}"
OUT_DIR="${OUT_DIR:-${WEKA_MOUNT}/sijial/results}"

# Base args from the config, excluding what the baseline overrides or that only
# apply with a served theorizer (no base_url / split models / per-run paths).
# Runs on the launch host (macOS = bash 3.2), so avoid process-substitution +
# heredoc; use a here-string over a shared helper instead.
CFG_FLAGS=()
if [ -n "$CONFIG" ] && [ -f "$CONFIG" ]; then
    while IFS= read -r _flag; do
        [ -n "$_flag" ] && CFG_FLAGS+=("$_flag")
    done <<EOF
$(python3 "$SCRIPT_DIR/_config_to_flags.py" "$CONFIG" \
    base_url theorizer_model execution_model belief_model \
    out_dir work_dir n_experiments dataset_metadata)
EOF
fi

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
    echo "Running baseline: $name (model=$MODEL, n=$N_EXPERIMENTS)"

    # shellcheck disable=SC2086
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
        --name="$name-$MODEL-baseline" \
        -- $RUN_CMD ${CFG_FLAGS[@]+"${CFG_FLAGS[@]}"} \
            --work_dir="work" \
            --out_dir="$OUT_DIR" \
            --dataset_metadata="$metadata" \
            --n_experiments="$N_EXPERIMENTS" \
            --theorizer_model="$MODEL" \
            --execution_model="$MODEL" \
            --belief_model="$BELIEF_MODEL" \
            --n_warmstart=0
done
