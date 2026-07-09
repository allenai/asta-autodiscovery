#!/usr/bin/env bash
#
# In-job entrypoint. Runs INSIDE a single GPU job:
#
#   1. spins up a local vLLM server for $MODEL on the job's GPU(s)
#   2. runs AutoDiscovery against http://localhost:$PORT/v1
#   3. tears the server down when the run finishes
#
# Co-locating the server and the run in one job avoids cross-job networking —
# the run talks to the server over localhost.
#
# Only the theorizer model ($MODEL) is served by vLLM and routed to it via
# --base_url; the --execution_model and --belief_model use their default
# endpoints (e.g. Vertex/OpenAI), matching the mixed setup (local theorizer +
# API execution/belief models).
#
# Driven by env vars set by the launcher:
#   MODEL             theorizer model / vLLM model   (default: Qwen/Qwen3.5-4B)
#   EXECUTION_MODEL   execution agents' model        (default: gemini-3.1-pro-preview)
#   BELIEF_MODEL      belief model (OpenAI)          (default: gpt-5-mini)
#   DATASET_METADATA  dataset metadata path/URL      (required)
#   N_EXPERIMENTS     number of MCTS iterations      (default: 4)
#   N_WARMSTART       warmstart experiments          (default: 0)
#   OUT_DIR           base output dir                (default: /weka/nora-default/sijial/results)
#                     Each run writes to OUT_DIR/<timestamp>/ containing the logs
#                     (mcts_nodes.json, temp_log.json, args.json), the agent
#                     work_dir (work/), and the vLLM server stdout (vllm.log).
#   WORK_DIR          agent work dir                 (default: OUT_DIR/<timestamp>/work)
#   PORT              local vLLM port                (default: 8000)
#   RUN_CMD           command that runs AutoDiscovery (default: python -m autodiscovery.run)
#   RUN_EXTRA_ARGS    extra flags appended to the run command
#   (plus everything serve_vllm.sh understands: GPU_COUNT, TP_SIZE,
#    MAX_MODEL_LEN, VLLM_VERSION, GDN_PREFILL_BACKEND, ...)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODEL="${MODEL:-Qwen/Qwen3.5-4B}"                       # theorizer, served by vLLM (via --base_url)
EXECUTION_MODEL="${EXECUTION_MODEL:-gemini-3.1-pro-preview}"  # execution agents, default endpoint
BELIEF_MODEL="${BELIEF_MODEL:-gpt-5-mini}"
N_EXPERIMENTS="${N_EXPERIMENTS:-4}"
N_WARMSTART="${N_WARMSTART:-0}"
OUT_DIR="${OUT_DIR:-/weka/nora-default/sijial/results}"
PORT="${PORT:-8000}"
RUN_CMD="${RUN_CMD:-python -m autodiscovery.run}"
: "${DATASET_METADATA:?DATASET_METADATA must be set}"

# Per-run directory under OUT_DIR: co-locate this run's logs, agent work_dir, and
# vLLM server stdout so everything for one run lives under results/<run>/.
RUN_TS="$(date -u +%Y%m%d-%H%M%S)"
RUN_DIR="${OUT_DIR%/}/${RUN_TS}"
WORK_DIR="${WORK_DIR:-$RUN_DIR/work}"
mkdir -p "$RUN_DIR" "$WORK_DIR"

cd "$REPO_ROOT"

# The vLLM --served-model-name must equal what the run sends as --model.
export PORT MODEL
export SERVED_NAME="${SERVED_NAME:-$MODEL}"
# Persist vLLM stdout into the run dir on weka, and log generated tokens (incl.
# reasoning) even when the structured/final answer is empty or unparseable.
export VLLM_LOG="${VLLM_LOG:-$RUN_DIR/vllm.log}"
export VLLM_ENABLE_LOG_OUTPUTS="${VLLM_ENABLE_LOG_OUTPUTS:-1}"

# shellcheck disable=SC2086
exec "$SCRIPT_DIR/serve_vllm.sh" -- \
    $RUN_CMD \
        --work_dir="$WORK_DIR" \
        --out_dir="$RUN_DIR" \
        --no-timestamp_dir \
        --dataset_metadata="$DATASET_METADATA" \
        --n_experiments="$N_EXPERIMENTS" \
        --theorizer_model="$MODEL" \
        --execution_model="$EXECUTION_MODEL" \
        --belief_model="$BELIEF_MODEL" \
        --base_url="http://localhost:${PORT}/v1" \
        --n_warmstart="$N_WARMSTART" \
        ${RUN_EXTRA_ARGS:-}
