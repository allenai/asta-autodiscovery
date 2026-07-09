#!/usr/bin/env bash
#
# Launch AutoDiscovery on Beaker with a local vLLM-served model as the theorizer
# (hypothesis generator), an API model for the execution agents, and an OpenAI
# model for beliefs.
#
# Single GPU job: gantry uploads the repo + installs the project, then runs
# scripts/vllm/serve_and_run_job.sh, which serves $MODEL with vLLM on the job's
# GPU and runs AutoDiscovery against http://localhost:$PORT/v1 (see that script
# for how the server and run are co-located). Only the theorizer --model goes to
# vLLM; --execution_model and --belief_model use their default endpoints.
#
# Override any var via the environment, then: bash scripts/vllm/launch_vllm_job.sh
#
# Prereqs (Beaker secrets in the workspace):
#   OPENAI_API_KEY  — for the belief model
#   HF_TOKEN        — to download the (possibly gated) model weights
#   AWS_*           — to read s3:// dataset metadata
#
# The HuggingFace cache lives on WEKA (bucket $WEKA_BUCKET, mounted at $WEKA_MOUNT)
# so weights download once and are reused across runs.
set -euo pipefail

# --- config (all overridable via env) ----------------------------------------
WORKSPACE="${WORKSPACE:-ai2/autodiscovery}"
CLUSTER="${CLUSTER:-ai2/rhea}"
BUDGET="${BUDGET:-ai2/asta}"
GPUS="${GPUS:-1}"
NAME="${NAME:-autodiscovery-vllm}"

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

# Always-passed env; the run-arg overrides are appended only when set so the
# config file (scripts/vllm/args.json) provides them otherwise.
ENV_ARGS=(
    --env "MODEL=$MODEL"
    --env "GDN_PREFILL_BACKEND=$GDN_PREFILL_BACKEND"
    --env "PORT=$PORT"
    --env "OUT_DIR=$OUT_DIR"
    --env "RUN_NAME=$NAME"
    --env "HF_HOME=$HF_CACHE"
    --env "HF_HUB_CACHE=$HF_CACHE/hub"
)
[ -n "${CONFIG:-}" ]                && ENV_ARGS+=( --env "CONFIG=$CONFIG" )
[ -n "${DATASET_METADATA:-}" ]      && ENV_ARGS+=( --env "DATASET_METADATA=$DATASET_METADATA" )
[ -n "${DATASET_METADATA_TYPE:-}" ] && ENV_ARGS+=( --env "DATASET_METADATA_TYPE=$DATASET_METADATA_TYPE" )
[ -n "${EXECUTION_MODEL:-}" ]       && ENV_ARGS+=( --env "EXECUTION_MODEL=$EXECUTION_MODEL" )
[ -n "${BELIEF_MODEL:-}" ]          && ENV_ARGS+=( --env "BELIEF_MODEL=$BELIEF_MODEL" )
[ -n "${N_EXPERIMENTS:-}" ]         && ENV_ARGS+=( --env "N_EXPERIMENTS=$N_EXPERIMENTS" )
[ -n "${N_WARMSTART:-}" ]           && ENV_ARGS+=( --env "N_WARMSTART=$N_WARMSTART" )
[ -n "${S3_RESULTS_PREFIX:-}" ]     && ENV_ARGS+=( --env "S3_RESULTS_PREFIX=$S3_RESULTS_PREFIX" )
[ -n "${MAX_MODEL_LEN:-}" ]         && ENV_ARGS+=( --env "MAX_MODEL_LEN=$MAX_MODEL_LEN" )
[ -n "${REASONING_PARSER+x}" ]      && ENV_ARGS+=( --env "REASONING_PARSER=$REASONING_PARSER" )

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
    --env-secret HF_TOKEN=HF_TOKEN \
    --env-secret AWS_ACCESS_KEY_ID=AWS_ACCESS_KEY_ID \
    --env-secret AWS_SECRET_ACCESS_KEY=AWS_SECRET_ACCESS_KEY \
    "${ENV_ARGS[@]}" \
    --name="$NAME" \
    -- bash scripts/vllm/serve_and_run_job.sh
