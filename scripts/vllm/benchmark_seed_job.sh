#!/usr/bin/env bash
#
# In-job: serve a Qwen theorizer via vLLM and run the L1 seed-determinism
# benchmark against it (benchmark_seed.py). Sends the same request N times with
# a fixed seed and reports whether outputs are identical. Runs two passes:
# structured (faithful to the real theorizer) and unstructured (pure sampling
# determinism), reusing one server load.
#
#   MODEL   theorizer / served model   (default: Qwen/Qwen3.5-9B)
#   PORT    local vLLM port            (default: 8000)
#   SEED    fixed sampling seed        (default: 42)
#   N       repeated calls per pass    (default: 3)
#   (plus everything serve_vllm.sh understands: GDN_PREFILL_BACKEND, MAX_MODEL_LEN, ...)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

if ! command -v uvx >/dev/null 2>&1; then
    echo "=== installing uv ==="
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

MODEL="${MODEL:-Qwen/Qwen3.5-9B}"
PORT="${PORT:-8000}"
SEED="${SEED:-42}"
N="${N:-3}"
export PORT MODEL
export SERVED_NAME="${SERVED_NAME:-$MODEL}"

cd "$REPO_ROOT"

BENCH="uv run --package asta-autodiscovery python scripts/vllm/benchmark_seed.py \
    --model $MODEL --base_url http://localhost:${PORT}/v1 --seed $SEED --n $N"

# Run both passes against a single served model. serve_vllm.sh starts the server,
# waits for readiness, runs the '--' command, then tears the server down.
exec "$SCRIPT_DIR/serve_vllm.sh" -- bash -c "
    set -e
    echo '########## PASS 1: structured (faithful theorizer request) ##########'
    $BENCH --structured || echo 'PASS1_NONDETERMINISTIC (exit non-zero)'
    echo
    echo '########## PASS 2: unstructured (pure sampling determinism) ##########'
    $BENCH --no-structured || echo 'PASS2_NONDETERMINISTIC (exit non-zero)'
"
