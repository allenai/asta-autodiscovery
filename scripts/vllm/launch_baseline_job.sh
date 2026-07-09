#!/usr/bin/env bash
#
# Launch AutoDiscovery baseline runs on Beaker with an OpenAI (or Gemini) model
# for both the agent and belief models — no local vLLM serving. Submits one
# gantry job per dataset.
#
# Usage:
#   # datasets as arguments
#   bash scripts/vllm/launch_baseline_job.sh <metadata-url> [<metadata-url> ...]
#
#   # or via the DATASETS env var (whitespace/newline separated)
#   DATASETS="a_metadata.json b_metadata.json" bash scripts/vllm/launch_baseline_job.sh
#
# Config (all overridable via env):
#   WORKSPACE      Beaker workspace     (default: ai2/autodiscovery)
#   CLUSTER        Beaker cluster       (default: ai2/phobos-cirrascale)
#   MODEL          agent model (theorizer + execution)  (default: gpt-5-mini)
#   BELIEF_MODEL   belief model         (default: = MODEL)
#   N_EXPERIMENTS  MCTS iterations      (default: 10)
#   RUN_CMD        run command          (default: python -m autodiscovery.run)
#   CLUSTER        Beaker cluster       (default: ai2/phobos-cirrascale; use an
#                  Austin cluster e.g. ai2/jupiter for the weka out_dir)
set -euo pipefail

WORKSPACE="${WORKSPACE:-ai2/autodiscovery}"
CLUSTER="${CLUSTER:-ai2/phobos-cirrascale}"
MODEL="${MODEL:-gpt-5-mini}"
BELIEF_MODEL="${BELIEF_MODEL:-$MODEL}"
N_EXPERIMENTS="${N_EXPERIMENTS:-10}"
RUN_CMD="${RUN_CMD:-python -m autodiscovery.run}"

# WEKA-backed output. Requires a cluster that mounts this weka (Austin clusters,
# e.g. ai2/jupiter); the default ai2/phobos-cirrascale does NOT, so override
# CLUSTER to an Austin cluster when using the weka out_dir.
WEKA_BUCKET="${WEKA_BUCKET:-nora-default}"
WEKA_MOUNT="${WEKA_MOUNT:-/weka/${WEKA_BUCKET}}"
OUT_DIR="${OUT_DIR:-${WEKA_MOUNT}/sijial/results}"

# Datasets from positional args, falling back to the DATASETS env var.
if [ "$#" -gt 0 ]; then
    datasets=("$@")
else
    # shellcheck disable=SC2206
    datasets=(${DATASETS:?provide dataset metadata paths as arguments or via DATASETS})
fi

for metadata in "${datasets[@]}"; do
    name="$(basename "$metadata" _metadata.json)"
    echo "Running $name"

    # shellcheck disable=SC2086
    gantry run --allow-dirty --workspace "$WORKSPACE" \
        --cluster "$CLUSTER" \
        --weka "${WEKA_BUCKET}:${WEKA_MOUNT}" \
        --timeout -1 \
        --task-timeout 24h \
        --not-preemptible \
        --env-secret OPENAI_API_KEY=OPENAI_API_KEY \
        --env-secret AWS_ACCESS_KEY_ID=AWS_ACCESS_KEY_ID \
        --env-secret AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY \
        --name="$name-$MODEL-baseline" \
        -- $RUN_CMD \
        --work_dir="work" \
        --out_dir="$OUT_DIR" \
        --dataset_metadata="$metadata" \
        --n_experiments="$N_EXPERIMENTS" \
        --theorizer_model="$MODEL" \
        --execution_model="$MODEL" \
        --belief_model="$BELIEF_MODEL" \
        --n_warmstart=0
done
