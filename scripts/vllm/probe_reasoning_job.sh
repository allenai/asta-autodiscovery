#!/usr/bin/env bash
#
# In-job: serve Qwen via vLLM with the reasoning parser OFF, then print the RAW,
# unparsed generation for a theorizer-shaped request (unstructured + structured).
# With the parser off, whatever the model emits (incl. any <think>...</think>) shows
# up verbatim in message.content, so we can see where the generated tokens actually
# go and whether the parser (when on) was dropping reasoning.
#
#   MODEL          served model            (default: Qwen/Qwen3.5-9B)
#   PORT           local vLLM port         (default: 8000)
#   MAX_MODEL_LEN  --max-model-len         (passed through to serve_vllm.sh)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

command -v uvx >/dev/null 2>&1 || curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

MODEL="${MODEL:-Qwen/Qwen3.5-9B}"
PORT="${PORT:-8000}"
export PORT MODEL
export SERVED_NAME="${SERVED_NAME:-$MODEL}"
export REASONING_PARSER=""   # parser OFF -> raw content includes any <think> block

cd "$REPO_ROOT"
PROBE="uv run --package asta-autodiscovery python scripts/vllm/probe_reasoning.py --model $MODEL --base_url http://localhost:${PORT}/v1"

# serve_vllm.sh starts the server (parser off), waits for readiness, runs the '--'
# command, then tears the server down.
exec "$SCRIPT_DIR/serve_vllm.sh" -- bash -c "
    set -e
    echo '########## RAW (parser OFF) — unstructured ##########'
    $PROBE || true
    echo
    echo '########## RAW (parser OFF) — structured (theorizer response_format) ##########'
    $PROBE --structured || true
"
