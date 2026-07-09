#!/usr/bin/env bash
#
# Local smoke test for the vLLM + AutoDiscovery pipeline, meant to be run by hand
# INSIDE an interactive Beaker GPU session (not via gantry). It exercises the exact
# same code path as the cluster job — serve $MODEL with vLLM on the session's GPU,
# run AutoDiscovery against http://localhost:$PORT/v1, tear the server down — but
# with a tiny N_EXPERIMENTS so you get a fast pass/fail before launching the job.
#
# Unlike the gantry job, an interactive session does NOT get secrets auto-injected,
# so this script reads them from the Beaker workspace and exports them itself
# (only if not already set in the environment).
#
# Usage (from the repo root, in a session with a GPU):
#   DATASET_METADATA=<path/url> bash scripts/vllm/smoke_test_local.sh
#
# Override any default inline, e.g. a different model or more experiments:
#   MODEL=Qwen/Qwen3-4B N_EXPERIMENTS=2 bash scripts/vllm/smoke_test_local.sh
#
# Config (all via env vars):
#   MODEL             agent model / vLLM model   (default: Qwen/Qwen3.5-4B)
#   BELIEF_MODEL      belief model (OpenAI)      (default: gpt-5-mini)
#   DATASET_METADATA  dataset metadata path/URL  (required)
#   N_EXPERIMENTS     MCTS iterations            (default: 1 — keep it small)
#   N_WARMSTART       warmstart experiments      (default: 0)
#   OUT_DIR           output dir                 (default: /weka/nora-default/sijial/results)
#   WORK_DIR          agent work dir             (default: /tmp/autods-local/work)
#   PORT              local vLLM port            (default: 8000)
#   SECRET_WORKSPACE  workspace to read secrets  (default: ai2/autodiscovery)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --- config (matches launch_vllm_job.sh, but tiny) ---------------------------
export MODEL="${MODEL:-Qwen/Qwen3.5-4B}"
export BELIEF_MODEL="${BELIEF_MODEL:-gpt-5-mini}"
export DATASET_METADATA="${DATASET_METADATA:?set DATASET_METADATA to your dataset metadata path/URL}"
export N_EXPERIMENTS="${N_EXPERIMENTS:-1}"
export N_WARMSTART="${N_WARMSTART:-0}"
export OUT_DIR="${OUT_DIR:-/weka/nora-default/sijial/results}"
export WORK_DIR="${WORK_DIR:-/tmp/autods-local/work}"
export PORT="${PORT:-8000}"
SECRET_WORKSPACE="${SECRET_WORKSPACE:-ai2/autodiscovery}"
# -----------------------------------------------------------------------------

log() { printf '\n=== [%s] smoke_test: %s ===\n' "$(date -u +%H:%M:%S)" "$*"; }

# GPU is required — vLLM won't serve without one. Warn loudly rather than hang.
if ! command -v nvidia-smi >/dev/null 2>&1 || ! nvidia-smi -L >/dev/null 2>&1; then
    log "WARNING: no GPU detected (nvidia-smi missing/failing). vLLM needs a GPU."
    log "Are you inside an interactive Beaker session with --gpus >= 1?"
fi

# Pull secrets from the workspace and export them, but never clobber a value the
# caller already set, and never print the secret. HF_TOKEN is optional (ungated
# weights need none) so a missing one is a warning, not fatal.
fetch_secret() {
    local name="$1" required="$2"
    if [ -n "${!name:-}" ]; then
        log "$name already set in env — using that"
        return 0
    fi
    local val
    if val="$(beaker secret read "$name" -w "$SECRET_WORKSPACE" 2>/dev/null)" && [ -n "$val" ]; then
        export "$name=$val"
        log "$name loaded from $SECRET_WORKSPACE"
    elif [ "$required" = required ]; then
        log "ERROR: required secret '$name' not found in $SECRET_WORKSPACE and not in env"
        exit 1
    else
        log "note: optional secret '$name' not found — continuing without it"
    fi
}

log "loading secrets from $SECRET_WORKSPACE"
fetch_secret OPENAI_API_KEY       required   # belief model
fetch_secret AWS_ACCESS_KEY_ID    required   # s3 dataset metadata
fetch_secret AWS_SECRET_ACCESS_KEY required
fetch_secret HF_TOKEN             optional   # only for gated weights

mkdir -p "$OUT_DIR" "$WORK_DIR"

log "serving '$MODEL' (belief=$BELIEF_MODEL), running $N_EXPERIMENTS experiment(s)"
log "out=$OUT_DIR work=$WORK_DIR port=$PORT"

# Delegate to the exact in-job entrypoint so this stays faithful to the cluster
# run. It reads the env vars we exported above.
cd "$REPO_ROOT"
exec bash "$SCRIPT_DIR/serve_and_run_job.sh"
