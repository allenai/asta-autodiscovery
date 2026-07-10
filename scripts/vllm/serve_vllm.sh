#!/usr/bin/env bash
#
# Serve any HF model with vLLM on the local GPU(s) as an OpenAI-compatible
# endpoint, then optionally run a client command against it.
#
# vLLM runs in an isolated uvx environment, so it does NOT touch the project's
# Python env. The only host requirement is an NVIDIA driver.
#
# Usage:
#   # serve only — blocks until killed (good for a standalone server / debugging)
#   MODEL=Qwen/Qwen3-4B scripts/vllm/serve_vllm.sh
#
#   # serve, run a client against it, then tear the server down
#   MODEL=Qwen/Qwen3-4B scripts/vllm/serve_vllm.sh -- \
#       <your client command> --base_url=http://localhost:8000/v1 ...
#
# Config (all via env vars; only MODEL really matters):
#   MODEL           HF model id or local path        (default: Qwen/Qwen3.5-4B)
#   SERVED_NAME     --served-model-name              (default: = MODEL; must match
#                                                     what the client passes as --model)
#   PORT            server port                      (default: 8000)
#   GPU_COUNT       GPUs to use                      (default: detected via nvidia-smi, else 1)
#   TP_SIZE         tensor-parallel size             (default: = GPU_COUNT)
#   MAX_MODEL_LEN   --max-model-len                  (default: vLLM auto)
#   GPU_MEM_UTIL    --gpu-memory-utilization         (default: 0.85)
#   VLLM_VERSION    vLLM version for uvx             (default: 0.23.0)
#   GDN_PREFILL_BACKEND  --gdn-prefill-backend value (default: unset; set to e.g.
#                                                     "triton" for Qwen3.5 GDN to
#                                                     avoid the flashinfer nvcc JIT)
#   VLLM_EXTRA_ARGS extra flags appended to `vllm serve`
#   HEALTH_TIMEOUT  seconds to wait for readiness    (default: 1800)
#   HEARTBEAT_INTERVAL  seconds between server pings during the run (default: 5)
#   VLLM_LOG        if set, also tee vLLM stdout to this file (default: unset)
#   VLLM_ENABLE_LOG_OUTPUTS  1 => --enable-log-outputs, logging each request's
#                            generated text incl. reasoning tokens (default: 0)
#   REASONING_PARSER  --reasoning-parser value; extracts <think>...</think> into a
#                     separate reasoning_content field (default: qwen3; set empty
#                     to disable, e.g. for non-Qwen models)
#   ENABLE_THINKING   1 => --default-chat-template-kwargs '{"enable_thinking":true}',
#                     turning thinking on by default for every request (default: 1).
#                     NOTE: reasoning_effort (low/medium/high) is NOT a serve flag —
#                     it is a per-request param the client sets; medium is the
#                     project default (run_mcts reasoning_effort="medium").
#
# vLLM's own stdout/stderr (incl. crash/OOM tracebacks) is streamed inline to
# this script's stdout, prefixed with '[vllm]'. While the client runs, a
# background heartbeat pings /v1/models every HEARTBEAT_INTERVAL seconds and
# logs ALIVE/DOWN, so a mid-run server death is timestamped in the same log
# stream rather than hidden in a separate file.

set -euo pipefail

log() { printf '\n=== [%s] serve_vllm: %s ===\n' "$(date -u +%H:%M:%S)" "$*"; }

# Put the repo root on PYTHONPATH so a client invoked by relative path can still
# resolve project imports. Harmless for any other client command.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="${REPO_ROOT}${PYTHONPATH:+:$PYTHONPATH}"

MODEL="${MODEL:-Qwen/Qwen3.5-4B}"
SERVED_NAME="${SERVED_NAME:-$MODEL}"
PORT="${PORT:-8000}"
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.85}"
VLLM_VERSION="${VLLM_VERSION:-0.23.0}"
HEALTH_TIMEOUT="${HEALTH_TIMEOUT:-1800}"
HEARTBEAT_INTERVAL="${HEARTBEAT_INTERVAL:-5}"
# If set, vLLM stdout (already streamed inline) is ALSO tee'd to this file.
VLLM_LOG="${VLLM_LOG:-}"
# 1 => pass --enable-log-outputs so vLLM logs each request's generated text.
# This captures the raw generation (including <think> reasoning tokens) even when
# the final/structured answer is empty or unparseable — useful for debugging the
# experiment_generator's silent parse failures.
VLLM_ENABLE_LOG_OUTPUTS="${VLLM_ENABLE_LOG_OUTPUTS:-0}"
# Qwen3-family reasoning: parse <think> blocks into reasoning_content and turn
# thinking on by default for every request. Set REASONING_PARSER= (empty, exported)
# to disable the parser (e.g. non-Qwen models, or to inspect raw output). Use "-"
# not ":-" so an explicit empty value disables rather than re-defaulting to qwen3.
REASONING_PARSER="${REASONING_PARSER-qwen3}"
ENABLE_THINKING="${ENABLE_THINKING:-1}"

# Detect GPU count if not provided.
if [ -z "${GPU_COUNT:-}" ]; then
    if command -v nvidia-smi >/dev/null 2>&1; then
        GPU_COUNT="$(nvidia-smi -L 2>/dev/null | grep -c '^GPU' || echo 1)"
    else
        GPU_COUNT=1
    fi
fi
[ "${GPU_COUNT:-0}" -ge 1 ] 2>/dev/null || GPU_COUNT=1
TP_SIZE="${TP_SIZE:-$GPU_COUNT}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-262144}"

# Ensure uv/uvx is available (isolated vLLM env; does not pollute the project env).
if ! command -v uvx >/dev/null 2>&1; then
    log "installing uv (uvx not found)"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# Pin fastapi < 0.137: 0.137 changed router internals and breaks
# prometheus-fastapi-instrumentator (mounted by vLLM on every route), making the
# API server 500 on every request incl. /v1/models. See vllm-project/vllm#45596.
VLLM_CMD=( uvx --with "fastapi<0.137" "vllm==${VLLM_VERSION}" serve "$MODEL"
           --served-model-name "$SERVED_NAME"
           --port "$PORT"
           --gpu-memory-utilization "$GPU_MEM_UTIL"
           --tensor-parallel-size "$TP_SIZE" )
# Optional: force a specific GDN prefill backend (e.g. "triton" for Qwen3.5 GDN,
# which otherwise triggers a slow flashinfer nvcc JIT compile).
[ -n "${GDN_PREFILL_BACKEND:-}" ] && VLLM_CMD+=( --gdn-prefill-backend "$GDN_PREFILL_BACKEND" )
[ -n "${MAX_MODEL_LEN:-}" ] && VLLM_CMD+=( --max-model-len "$MAX_MODEL_LEN" )
# Log each request's generated text (incl. reasoning tokens) to vLLM stdout.
# --enable-log-outputs requires --enable-log-requests (vLLM validates this pair).
[ "${VLLM_ENABLE_LOG_OUTPUTS:-0}" = "1" ] && VLLM_CMD+=( --enable-log-requests --enable-log-outputs )
# shellcheck disable=SC2206
[ -n "${VLLM_EXTRA_ARGS:-}" ] && VLLM_CMD+=( ${VLLM_EXTRA_ARGS} )

log "serving '$MODEL' on :$PORT (GPUs=$GPU_COUNT, TP=$TP_SIZE, vLLM=$VLLM_VERSION)"
log "cmd: ${VLLM_CMD[*]}"
# Stream vLLM's output inline (prefixed) so crash/OOM tracebacks land in this
# same log. If VLLM_LOG is set, also tee the (prefixed) stream to that file so
# it persists per-run (e.g. under the weka results dir). The process
# substitution keeps $! pointing at the vLLM process itself (not the subshell).
if [ -n "$VLLM_LOG" ]; then
    mkdir -p "$(dirname "$VLLM_LOG")"
    log "also writing vLLM stdout to $VLLM_LOG"
    "${VLLM_CMD[@]}" > >(sed 's/^/[vllm] /' | tee -a "$VLLM_LOG") 2>&1 &
else
    "${VLLM_CMD[@]}" > >(sed 's/^/[vllm] /') 2>&1 &
fi
VLLM_PID=$!

HEARTBEAT_PID=""
cleanup() {
    [ -n "$HEARTBEAT_PID" ] && kill "$HEARTBEAT_PID" 2>/dev/null || true
    log "stopping vllm (pid $VLLM_PID)"
    kill "$VLLM_PID" 2>/dev/null || true
    wait "$VLLM_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

log "waiting for vllm /v1/models (up to ${HEALTH_TIMEOUT}s)"
deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
until curl -sf "http://localhost:$PORT/v1/models" >/dev/null 2>&1; do
    if ! kill -0 "$VLLM_PID" 2>/dev/null; then
        log "vllm process died during startup — see the [vllm] output above"
        exit 1
    fi
    if [ "$(date +%s)" -ge "$deadline" ]; then
        log "vllm not ready within ${HEALTH_TIMEOUT}s — see the [vllm] output above"
        exit 1
    fi
    sleep 5
done
log "vllm ready at http://localhost:$PORT/v1 (model name: $SERVED_NAME)"

# Heartbeat: ping the server every HEARTBEAT_INTERVAL seconds for the rest of
# the run, so a mid-run death is timestamped inline. Runs until cleanup kills it.
heartbeat_loop() {
    while true; do
        if curl -sf "http://localhost:$PORT/v1/models" >/dev/null 2>&1; then
            printf '=== [%s] vllm-ping: ALIVE :%s ===\n' "$(date -u +%H:%M:%S)" "$PORT"
        else
            alive=no; kill -0 "$VLLM_PID" 2>/dev/null && alive=yes
            printf '=== [%s] vllm-ping: DOWN  :%s (server pid %s alive=%s) ===\n' \
                "$(date -u +%H:%M:%S)" "$PORT" "$VLLM_PID" "$alive"
        fi
        sleep "$HEARTBEAT_INTERVAL"
    done
}
heartbeat_loop &
HEARTBEAT_PID=$!
log "heartbeat pinging :$PORT every ${HEARTBEAT_INTERVAL}s (pid $HEARTBEAT_PID)"

# If a command follows `--`, run it against the live server, then tear down.
if [ "${1:-}" = "--" ]; then
    shift
    log "running client: $*"
    set +e
    "$@"
    exit_code=$?
    set -e
    log "client exited ($exit_code)"
    # On client failure, surface the vLLM state: a mid-run crash (e.g. GPU OOM)
    # shows up client-side only as 'Connection refused'. The [vllm] output and
    # vllm-ping heartbeat above already timestamp the death; just say which case.
    if [ "$exit_code" -ne 0 ]; then
        if kill -0 "$VLLM_PID" 2>/dev/null; then
            log "vllm (pid $VLLM_PID) still alive — client failed for another reason"
        else
            log "vllm (pid $VLLM_PID) is DEAD — it died during the run (likely why the client saw 'Connection refused'); see the [vllm]/vllm-ping output above"
        fi
    fi
    exit "$exit_code"
fi

# Serve-only mode: block until the server exits or is killed.
log "serve-only mode; kill pid $VLLM_PID (or Ctrl-C) to stop"
wait "$VLLM_PID"
