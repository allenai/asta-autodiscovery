#!/usr/bin/env bash
#
# Launch AutoDiscovery on Beaker with a local vLLM-served model as the theorizer
# (hypothesis generator), an API model for the execution agents, and an OpenAI
# model for beliefs.
#
# Submits one single-GPU gantry job per dataset (see DEFAULT_DATASETS). For each,
# gantry uploads the repo + installs the project, then runs
# scripts/vllm/serve_and_run_job.sh, which serves $MODEL with vLLM on the job's
# GPU and runs AutoDiscovery against http://localhost:$PORT/v1 (see that script
# for how the server and run are co-located). Only the theorizer --model goes to
# vLLM; --execution_model and --belief_model use their default endpoints.
#
# Usage:
#   # default set (TCGA Breast + TCGA Melanoma [asta], NLS Raw [dbench]) -> 3 jobs:
#   bash scripts/vllm/launch_vllm_job.sh
#   # or override with explicit datasets (typeless; type falls back to the config):
#   bash scripts/vllm/launch_vllm_job.sh <metadata-url> [<metadata-url> ...]
#   DATASETS="a.json b.json" bash scripts/vllm/launch_vllm_job.sh
#
# Default datasets and their metadata types are set in DEFAULT_DATASETS below.
# Override any other var via the environment.
#
# Prereqs (Beaker secrets in the workspace):
#   OPENAI_API_KEY  — for the belief model
#   HF_TOKEN        — to download the (possibly gated) model weights
#   AWS_*           — to read s3:// dataset metadata
#
# The HuggingFace cache lives on WEKA (bucket $WEKA_BUCKET, mounted at $WEKA_MOUNT)
# so weights download once and are reused across runs.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- config (all overridable via env) ----------------------------------------
WORKSPACE="${WORKSPACE:-ai2/autodiscovery}"
CLUSTER="${CLUSTER:-ai2/jupiter}"
BUDGET="${BUDGET:-ai2/asta}"
GPUS="${GPUS:-1}"

# Run args default to scripts/vllm/args.json (loaded by serve_and_run_job.sh).
# The env vars below are OPTIONAL overrides — each one, when set, REPLACES the
# corresponding value from the config file. Leave them unset to use the config.
MODEL="${MODEL:-Qwen/Qwen3.5-9B}"          # theorizer, served by vLLM (must match the config's theorizer_model)
# Qwen3.5 uses Gated DeltaNet; force the Triton GDN prefill backend to avoid the
# flashinfer nvcc JIT compile (no CUDA toolkit in the container). Set to "" for
# non-GDN models.
GDN_PREFILL_BACKEND="${GDN_PREFILL_BACKEND:-triton}"
PORT="${PORT:-8000}"
# MAX_MODEL_LEN=32768                       # uncomment to cap context (passed through to vLLM)

# WEKA-backed HuggingFace cache. Point these at your own workspace/bucket.
WEKA_BUCKET="${WEKA_BUCKET:-nora-default}"
WEKA_MOUNT="${WEKA_MOUNT:-/weka/${WEKA_BUCKET}}"
HF_CACHE="${HF_CACHE:-${WEKA_MOUNT}/hf-cache}"
OUT_DIR="${OUT_DIR:-${WEKA_MOUNT}/sijial/results}"
# -----------------------------------------------------------------------------

# --- run name: <tag>-<dataset>-cfg-n<N>, matching the baseline convention
# (e.g. qwen9b-tcga-breast-cfg-n10). Built from the model tag + each dataset's
# metadata + n_experiments (env N_EXPERIMENTS wins). Override the whole name via
# NAME (single dataset), or just the model tag via TAG. -----------------------
CONFIG_PATH="${CONFIG:-$SCRIPT_DIR/args.json}"
_cfg_get() {  # _cfg_get <key>: echo the config value ("" if absent / no config)
    [ -f "$CONFIG_PATH" ] || return 0
    python3 -c 'import json,sys; v=json.load(open(sys.argv[1])).get(sys.argv[2]); print("" if v is None else v)' \
        "$CONFIG_PATH" "$1" || true
}
# Model tag: Qwen/Qwen3.5-9B -> qwen9b (family + trailing <N>b size).
_model_lc="$(basename "$MODEL" | tr '[:upper:]' '[:lower:]')"
_tag_fam="$(printf '%s' "$_model_lc" | sed -E 's/[0-9].*$//')"
_tag_size="$(printf '%s' "$_model_lc" | grep -oE '[0-9]+b' | tail -1 || true)"
TAG="${TAG:-${_tag_fam}${_tag_size}}"
_n_exp="${N_EXPERIMENTS:-$(_cfg_get n_experiments)}"

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

# Dataset-independent env; the run-arg overrides are appended only when set so
# the config file (scripts/vllm/args.json) provides them otherwise. Per-dataset
# env (DATASET_METADATA[_TYPE], RUN_NAME) is added inside the loop below.
ENV_ARGS=(
    --env "MODEL=$MODEL"
    --env "GDN_PREFILL_BACKEND=$GDN_PREFILL_BACKEND"
    --env "PORT=$PORT"
    --env "OUT_DIR=$OUT_DIR"
    --env "HF_HOME=$HF_CACHE"
    --env "HF_HUB_CACHE=$HF_CACHE/hub"
)
[ -n "${CONFIG:-}" ]            && ENV_ARGS+=( --env "CONFIG=$CONFIG" )
[ -n "${EXECUTION_MODEL:-}" ]  && ENV_ARGS+=( --env "EXECUTION_MODEL=$EXECUTION_MODEL" )
[ -n "${BELIEF_MODEL:-}" ]     && ENV_ARGS+=( --env "BELIEF_MODEL=$BELIEF_MODEL" )
[ -n "${N_EXPERIMENTS:-}" ]    && ENV_ARGS+=( --env "N_EXPERIMENTS=$N_EXPERIMENTS" )
[ -n "${N_WARMSTART:-}" ]      && ENV_ARGS+=( --env "N_WARMSTART=$N_WARMSTART" )
[ -n "${S3_RESULTS_PREFIX:-}" ] && ENV_ARGS+=( --env "S3_RESULTS_PREFIX=$S3_RESULTS_PREFIX" )
[ -n "${MAX_MODEL_LEN:-}" ]    && ENV_ARGS+=( --env "MAX_MODEL_LEN=$MAX_MODEL_LEN" )
[ -n "${REASONING_PARSER+x}" ] && ENV_ARGS+=( --env "REASONING_PARSER=$REASONING_PARSER" )

for entry in "${entries[@]}"; do
    dtype="${entry%%|*}"
    metadata="${entry#*|}"
    [ -n "$metadata" ] || { echo "empty dataset entry; skipping" >&2; continue; }

    dataset_short="$(dataset_stem "$metadata")"
    run_name="${NAME:-${TAG}-${dataset_short}-cfg-n${_n_exp}}"
    echo "Running vLLM: $run_name (model=$MODEL, n=${_n_exp}, type=${dtype:-<config>}, metadata=$metadata)"

    # Per-dataset metadata type override (empty -> keep the config's value).
    type_env=()
    [ -n "$dtype" ] && type_env=( --env "DATASET_METADATA_TYPE=$dtype" )

    gantry run --allow-dirty --workspace "$WORKSPACE" \
        --cluster "$CLUSTER" \
        --budget "$BUDGET" \
        --no-python \
        --gpus "$GPUS" \
        --weka "${WEKA_BUCKET}:${WEKA_MOUNT}" \
        --priority "${PRIORITY:-urgent}" \
        --timeout -1 \
        --task-timeout 24h \
        --env-secret OPENAI_API_KEY=OPENAI_API_KEY \
        --env-secret HF_TOKEN=HF_TOKEN \
        --env-secret AWS_ACCESS_KEY_ID=AWS_ACCESS_KEY_ID \
        --env-secret AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY \
        "${ENV_ARGS[@]}" \
        --env "DATASET_METADATA=$metadata" \
        ${type_env[@]+"${type_env[@]}"} \
        --env "RUN_NAME=$run_name" \
        --name="$run_name" \
        -- bash scripts/vllm/serve_and_run_job.sh
done
