#!/usr/bin/env bash
# End-to-end smoke test for the slime surprisal-reward wiring, no LLM/GPU/GCP.
#
# Starts the reward server with the scorer stubbed (mock_reward_server.py),
# then drives the real HTTP contract that slime's rm_hub/autodiscovery.py speaks:
# per-dataset routing, request_id dedup, unknown-dataset rejection. Meant to be
# run inside a Beaker session (or any box with the autodiscovery env) before
# committing real training budget.
#
# Usage:
#   uv run bash scripts/slime/mock_reward_e2e.sh
#   PORT=9001 PYTHON="uv run python" bash scripts/slime/mock_reward_e2e.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8137}"
HOST="${HOST:-127.0.0.1}"
PY="${PYTHON:-python}"
BASE="http://${HOST}:${PORT}"

TMP="$(mktemp -d)"
SERVER_PID=""
cleanup() {
    [ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true
    rm -rf "$TMP"
}
trap cleanup EXIT

# Two datasets; paths are fake — the mock scorer never opens them.
cat >"$TMP/registry.json" <<JSON
{
  "tcga-breast":   "$TMP/fake/breast/metadata.json",
  "tcga-melanoma": "$TMP/fake/melanoma/metadata.json"
}
JSON

echo "[mock-e2e] starting server on $BASE ..."
$PY "$DIR/mock_reward_server.py" \
    --dataset_registry "$TMP/registry.json" \
    --host "$HOST" --port "$PORT" --concurrency 2 \
    >"$TMP/server.log" 2>&1 &
SERVER_PID=$!

# Wait for /health (server import pulls in autodiscovery, can take a few s).
for _ in $(seq 1 60); do
    if curl -sf "$BASE/health" >/dev/null 2>&1; then break; fi
    if ! kill -0 "$SERVER_PID" 2>/dev/null; then
        echo "[mock-e2e] server died on startup:"; cat "$TMP/server.log"; exit 1
    fi
    sleep 1
done

echo "[mock-e2e] server up; running checks ..."
BASE="$BASE" $PY - <<'PY'
import json, os, urllib.error, urllib.request

BASE = os.environ["BASE"]


def call(path, payload=None, method="GET"):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"}, method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def reward(hypothesis, dataset_id=None, request_id=None):
    body = {"hypothesis": hypothesis}
    if dataset_id is not None:
        body["dataset_id"] = dataset_id
    if request_id is not None:
        body["request_id"] = request_id
    return call("/reward", body, method="POST")

# 1. health lists both datasets
st, h = call("/health")
assert st == 200 and h["datasets"] == ["tcga-breast", "tcga-melanoma"], h
print("  [ok] /health ->", h["datasets"])

# 2. routing: each dataset_id returns a scored reward tagged with that dataset
st, r1 = reward("Taller plants make more seeds.", "tcga-breast", "req-1")
assert st == 200 and r1["success"] and r1["dataset_id"] == "tcga-breast"
assert isinstance(r1["reward"], float) and r1.get("mock") is True, r1
st, r2 = reward("Melanoma stage predicts survival.", "tcga-melanoma", "req-2")
assert st == 200 and r2["dataset_id"] == "tcga-melanoma", r2
print(f"  [ok] routing -> breast reward={r1['reward']:.3f}, melanoma reward={r2['reward']:.3f}")

# 3. dedup: same request_id served from cache (identical call_index)
st, dup1 = reward("Repeated hypothesis.", "tcga-breast", "req-dup")
st, dup2 = reward("Repeated hypothesis.", "tcga-breast", "req-dup")
assert dup1["call_index"] == dup2["call_index"], (dup1, dup2)
# 4. a fresh request_id actually re-runs the scorer (higher call_index)
st, fresh = reward("Repeated hypothesis.", "tcga-breast", "req-fresh")
assert fresh["call_index"] > dup1["call_index"], (dup1, fresh)
print(f"  [ok] dedup: req-dup call_index={dup1['call_index']} (cached), "
      f"req-fresh call_index={fresh['call_index']} (re-run)")

# 5. unknown dataset_id -> 400
st, err = reward("H", "does-not-exist", "req-x")
assert st == 400 and "unknown dataset_id" in err.get("error", ""), (st, err)
print("  [ok] unknown dataset_id -> 400")

# 6. omitted dataset_id with >1 dataset -> 400 (ambiguous)
st, err = reward("H", None, "req-y")
assert st == 400, (st, err)
print("  [ok] omitted dataset_id (ambiguous) -> 400")

print("ALL MOCK CHECKS PASSED")
PY

echo "[mock-e2e] done."
