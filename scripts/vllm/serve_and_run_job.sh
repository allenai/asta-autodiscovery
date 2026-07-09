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
# Base run args are loaded from a JSON config (CONFIG, default: the co-located
# scripts/vllm/args.json). The env vars below are OPTIONAL — each one, when set,
# REPLACES the corresponding value from the config file (argparse: last wins).
#   CONFIG            JSON args file (base defaults)  (default: <scriptdir>/args.json; "" to disable)
#   MODEL             theorizer / vLLM served model   (default: config's theorizer_model, else Qwen/Qwen3.5-9B)
#   EXECUTION_MODEL   execution agents' model         (override; else from config)
#   BELIEF_MODEL      belief model                    (override; else from config)
#   DATASET_METADATA[_TYPE]  dataset metadata + type  (override; else from config)
#   N_EXPERIMENTS     number of MCTS iterations       (override; else from config)
#   N_WARMSTART       warmstart experiments           (override; else from config)
#   OUT_DIR           base output dir                 (default: /weka/nora-default/sijial/results)
#                     Each run writes to OUT_DIR/<timestamp>/ containing the logs
#                     (mcts_nodes.json, temp_log.json, args.json), the agent
#                     work_dir (work/), and the vLLM server stdout (vllm.log).
#   WORK_DIR          agent work dir                  (default: OUT_DIR/<timestamp>/work)
#   PORT              local vLLM port                 (default: 8000)
#   RUN_CMD           command that runs AutoDiscovery (default: uv run --package asta-autodiscovery python -m autodiscovery.run)
#   RUN_EXTRA_ARGS    extra flags appended to the run command
#   S3_RESULTS_PREFIX after the run, sync OUT_DIR/<ts> here (default: s3://ai2-asta-workspaces/autods/runs; "" to disable)
#   (plus everything serve_vllm.sh understands: GPU_COUNT, TP_SIZE,
#    MAX_MODEL_LEN, VLLM_VERSION, GDN_PREFILL_BACKEND, ...)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Base run args come from this JSON config (co-located with the launcher). Its
# values are the defaults; the runtime paths and any explicitly-set env var below
# replace them (argparse: the last occurrence of a flag wins). Set CONFIG="" to
# run purely from env vars.
CONFIG="${CONFIG:-$SCRIPT_DIR/args.json}"

PORT="${PORT:-8000}"
OUT_DIR="${OUT_DIR:-/weka/nora-default/sijial/results}"
# Run the client through uv so the autodiscovery package + its workspace-sibling
# deps resolve from the uv workspace (this is a uv monorepo; plain `python -m`
# would not find the package). serve_vllm.sh ensures uv is installed.
RUN_CMD="${RUN_CMD:-uv run --package asta-autodiscovery python -m autodiscovery.run}"

# The served vLLM model IS the theorizer, so default MODEL from the config's
# theorizer_model (keeps serving in sync with the run); MODEL env overrides.
if [ -z "${MODEL:-}" ] && [ -n "$CONFIG" ] && [ -f "$CONFIG" ]; then
    MODEL="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("theorizer_model",""))' "$CONFIG" 2>/dev/null || true)"
fi
MODEL="${MODEL:-Qwen/Qwen3.5-9B}"

# Per-run directory under OUT_DIR: co-locate this run's logs, agent work_dir, and
# vLLM server stdout so everything for one run lives under results/<run>/.
RUN_TS="$(date -u +%Y%m%d-%H%M%S)"
RUN_DIR="${OUT_DIR%/}/${RUN_TS}"
WORK_DIR="${WORK_DIR:-$RUN_DIR/work}"
mkdir -p "$RUN_DIR" "$WORK_DIR"

cd "$REPO_ROOT"

# The vLLM --served-model-name must equal what the run sends as --theorizer_model.
export PORT MODEL
export SERVED_NAME="${SERVED_NAME:-$MODEL}"
# Persist vLLM stdout into the run dir on weka, and log generated tokens (incl.
# reasoning) even when the structured/final answer is empty or unparseable.
export VLLM_LOG="${VLLM_LOG:-$RUN_DIR/vllm.log}"
export VLLM_ENABLE_LOG_OUTPUTS="${VLLM_ENABLE_LOG_OUTPUTS:-1}"

# Build the run args: base from the config file (JSON -> --flags), then runtime
# and explicitly-set env overrides appended so they replace the file's values.
RUN_ARGS=()
if [ -n "$CONFIG" ] && [ -f "$CONFIG" ]; then
    echo "=== base run args from config: $CONFIG ==="
    while IFS= read -r _flag; do RUN_ARGS+=("$_flag"); done < <(
        python3 - "$CONFIG" <<'PY'
import json, sys
for k, v in json.load(open(sys.argv[1])).items():
    if v is None:
        continue                                # null -> leave argparse default
    if isinstance(v, bool):
        print(f"--{k}" if v else f"--no-{k}")   # all bools are BooleanOptionalAction
    else:
        print(f"--{k}={v}")
PY
    )
fi

# Runtime + serving-coupled flags always replace the config's values.
RUN_ARGS+=( --out_dir="$RUN_DIR" --work_dir="$WORK_DIR" --no-timestamp_dir
            --base_url="http://localhost:${PORT}/v1"
            --theorizer_model="$MODEL" )

# Explicit env overrides replace the config only when set.
[ -n "${EXECUTION_MODEL:-}" ] && RUN_ARGS+=( --execution_model="$EXECUTION_MODEL" )
[ -n "${BELIEF_MODEL:-}" ]    && RUN_ARGS+=( --belief_model="$BELIEF_MODEL" )
[ -n "${DATASET_METADATA:-}" ] && RUN_ARGS+=( --dataset_metadata="$DATASET_METADATA" )
[ -n "${DATASET_METADATA_TYPE:-}" ] && RUN_ARGS+=( --dataset_metadata_type="$DATASET_METADATA_TYPE" )
[ -n "${N_EXPERIMENTS:-}" ]   && RUN_ARGS+=( --n_experiments="$N_EXPERIMENTS" )
[ -n "${N_WARMSTART:-}" ]     && RUN_ARGS+=( --n_warmstart="$N_WARMSTART" )
# shellcheck disable=SC2206
[ -n "${RUN_EXTRA_ARGS:-}" ]  && RUN_ARGS+=( ${RUN_EXTRA_ARGS} )

# Run (not exec) so we can sync results to S3 after the run completes.
run_rc=0
# shellcheck disable=SC2086
"$SCRIPT_DIR/serve_vllm.sh" -- $RUN_CMD "${RUN_ARGS[@]}" || run_rc=$?

# Sync the finished run dir to S3 so results are downloadable off weka (the job
# has AWS_* secrets but no aws CLI, so run it via uvx). Best-effort: a sync
# failure never fails the run (outputs still persist on weka at $RUN_DIR).
# Set S3_RESULTS_PREFIX="" to disable.
S3_RESULTS_PREFIX="${S3_RESULTS_PREFIX:-s3://ai2-asta-workspaces/autods/runs}"
if [ -n "$S3_RESULTS_PREFIX" ]; then
    s3_dest="${S3_RESULTS_PREFIX%/}/${RUN_TS}/"
    echo "=== [$(date -u +%H:%M:%S)] syncing $RUN_DIR -> $s3_dest ==="
    if uvx --from awscli aws s3 sync "$RUN_DIR" "$s3_dest" --no-progress; then
        echo "=== s3 sync OK: $s3_dest ==="
    else
        echo "=== WARN: s3 sync failed; results remain on weka at $RUN_DIR ==="
    fi
fi

exit "$run_rc"
