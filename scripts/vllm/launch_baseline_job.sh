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
#   # default set (TCGA Breast + TCGA Melanoma [asta], NLS Raw [dbench]) -> 3 jobs:
#   bash scripts/vllm/launch_baseline_job.sh
#   # or override with explicit datasets (typeless; type falls back to the config):
#   bash scripts/vllm/launch_baseline_job.sh <metadata-url> [<metadata-url> ...]
#   DATASETS="a.json b.json" bash scripts/vllm/launch_baseline_job.sh
#
# Default datasets and their metadata types are set in DEFAULT_DATASETS below.
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
EXECUTION_MODEL="${EXECUTION_MODEL:-gpt-5-mini}"
BELIEF_MODEL="${BELIEF_MODEL:-$MODEL}"
N_EXPERIMENTS="${N_EXPERIMENTS:-50}"
CONFIG="${CONFIG:-$SCRIPT_DIR/args.json}"
GPUS="${GPUS:-0}"

# WEKA-backed output. Requires an Austin cluster that mounts this weka.
WEKA_BUCKET="${WEKA_BUCKET:-nora-default}"
WEKA_MOUNT="${WEKA_MOUNT:-/weka/${WEKA_BUCKET}}"
OUT_DIR="${OUT_DIR:-${WEKA_MOUNT}/sijial/results}"

# Default dataset_metadata_type (asta for the TCGA sets; dbench for DiscoveryBench)
# NLS Raw uses a single DiscoveryBench task (metadata_2.json of metadata_2..8).
DEFAULT_DATASETS=(
    "asta|s3://ai2-asta-workspaces/autods/datasets/tcga-breast-cancer/tcga_breast_cancer_metadata.json"
    "asta|s3://ai2-asta-workspaces/autods/datasets/tcga-melanoma/tcga_melanoma_metadata.json"
    "dbench|s3://ai2-asta-workspaces/autods/datasets/discoverybench/real/test/nls_raw/metadata_2.json"
)

entries=()
if [ "$#" -gt 0 ]; then
    for d in "$@"; do entries+=("|$d"); done
elif [ -n "${DATASETS:-}" ]; then
    # shellcheck disable=SC2206
    for d in ${DATASETS}; do entries+=("|$d"); done
else
    entries=("${DEFAULT_DATASETS[@]}")
fi

# Run-name stem from a metadata url
dataset_stem() {
    local url="$1" base parent
    base="$(basename "$url")"
    if [ "$base" != "${base%_metadata.json}" ]; then
        base="${base%_metadata.json}"
    else
        parent="$(basename "$(dirname "$url")")"
        base="${parent}-${base%.json}"
    fi
    echo "$base" | sed -e 's/_cancer$//' -e 's/_/-/g'
}

for entry in "${entries[@]}"; do
    dtype="${entry%%|*}"
    metadata="${entry#*|}"
    [ -n "$metadata" ] || { echo "empty dataset entry; skipping" >&2; continue; }

    dataset_short="$(dataset_stem "$metadata")"
    run_name="${NAME:-baseline-${dataset_short}-n${N_EXPERIMENTS}}"
    echo "Running baseline: $run_name (model=$MODEL, n=$N_EXPERIMENTS, type=${dtype:-<config>}, metadata=$metadata)"

    type_env=()
    [ -n "$dtype" ] && type_env=( --env "DATASET_METADATA_TYPE=$dtype" )

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
        ${type_env[@]+"${type_env[@]}"} \
        --env "RUN_NAME=$run_name" \
        --name="$run_name" \
        -- bash scripts/vllm/run_baseline_job.sh
done
