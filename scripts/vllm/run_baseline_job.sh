#!/usr/bin/env bash
#
# In-job entrypoint for the API-only BASELINE (no local vLLM). Runs INSIDE a
# single Beaker job:
#
#   1. bootstraps uv (the --no-python base image has none; the vLLM path gets
#      uv from serve_vllm.sh, but the baseline has no server to piggyback on)
#   2. runs AutoDiscovery with ONE API model for all agents (theorizer =
#      execution = MODEL), belief = BELIEF_MODEL, using each model's DEFAULT
#      endpoint (no --base_url)
#   3. syncs the finished run dir to S3
#
# Mirrors serve_and_run_job.sh (same per-run layout + S3 sync) minus the vLLM
# server, so baseline and vLLM/Qwen runs share hyperparameters and output shape
# for a fair comparison.
#
# Base run args are loaded from a JSON config (CONFIG, default: the co-located
# scripts/vllm/args.json). The vLLM-only keys (base_url) and the split-model /
# per-run-path keys are dropped or overridden here. Env vars below, when set,
# REPLACE the config's value (argparse: last wins).
#   CONFIG           JSON args file (base defaults)  (default: <scriptdir>/args.json; "" to disable)
#   MODEL            single baseline model (theorizer = execution)  (default: gpt-5-mini)
#   BELIEF_MODEL     belief model                    (default: = MODEL)
#   DATASET_METADATA[_TYPE]  dataset metadata + type (override; else from config)
#   N_EXPERIMENTS    number of MCTS iterations       (override; else from config)
#   N_WARMSTART      warmstart experiments           (default: 0)
#   OUT_DIR          base output dir                 (default: /weka/nora-default/sijial/results)
#                    Each run writes to OUT_DIR/<timestamp>/ (logs + agent work/).
#   WORK_DIR         agent work dir                  (default: OUT_DIR/<timestamp>/work)
#   RUN_CMD          command that runs AutoDiscovery (default: uv run --package asta-autodiscovery python -m autodiscovery.run)
#   RUN_EXTRA_ARGS   extra flags appended to the run command
#   S3_RESULTS_PREFIX after the run, sync OUT_DIR/<ts> here (default: s3://ai2-asta-workspaces/autods/runs; "" to disable)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# --no-python base image ships no uv; install it (same source as serve_vllm.sh).
if ! command -v uv >/dev/null 2>&1; then
    echo "=== installing uv ==="
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

CONFIG="${CONFIG:-$SCRIPT_DIR/args.json}"
MODEL="${MODEL:-gpt-5-mini}"
BELIEF_MODEL="${BELIEF_MODEL:-$MODEL}"
OUT_DIR="${OUT_DIR:-/weka/nora-default/sijial/results}"
RUN_CMD="${RUN_CMD:-uv run --package asta-autodiscovery python -m autodiscovery.run}"

# Per-run directory under OUT_DIR: co-locate logs and the agent work_dir. The
# work_dir MUST be absolute — the sandbox chdir's into it, and a relative path
# (e.g. work/<ts>) fails to resolve there.
RUN_TS="$(date -u +%Y%m%d-%H%M%S)"
RUN_DIR="${OUT_DIR%/}/${RUN_TS}"
WORK_DIR="${WORK_DIR:-$RUN_DIR/work}"
mkdir -p "$RUN_DIR" "$WORK_DIR"

cd "$REPO_ROOT"

# Base args from the config, dropping the vLLM-only key (base_url) and the keys
# this script overrides below (models, per-run paths, timestamp, dataset, n).
RUN_ARGS=()
if [ -n "$CONFIG" ] && [ -f "$CONFIG" ]; then
    echo "=== base run args from config: $CONFIG ==="
    while IFS= read -r _flag; do RUN_ARGS+=("$_flag"); done < <(
        python3 "$SCRIPT_DIR/_config_to_flags.py" "$CONFIG" \
            base_url theorizer_model execution_model belief_model \
            out_dir work_dir timestamp_dir dataset_metadata n_experiments n_warmstart
    )
fi

# Runtime paths + single-model baseline settings always replace the config.
RUN_ARGS+=( --out_dir="$RUN_DIR" --work_dir="$WORK_DIR" --no-timestamp_dir
            --theorizer_model="$MODEL" --execution_model="$MODEL"
            --belief_model="$BELIEF_MODEL"
            --n_warmstart="${N_WARMSTART:-0}" )

# Explicit env overrides replace the config only when set.
[ -n "${DATASET_METADATA:-}" ]      && RUN_ARGS+=( --dataset_metadata="$DATASET_METADATA" )
[ -n "${DATASET_METADATA_TYPE:-}" ] && RUN_ARGS+=( --dataset_metadata_type="$DATASET_METADATA_TYPE" )
[ -n "${N_EXPERIMENTS:-}" ]         && RUN_ARGS+=( --n_experiments="$N_EXPERIMENTS" )
# shellcheck disable=SC2206
[ -n "${RUN_EXTRA_ARGS:-}" ]        && RUN_ARGS+=( ${RUN_EXTRA_ARGS} )

# Run (not exec) so we can sync results to S3 afterwards.
run_rc=0
# shellcheck disable=SC2086
$RUN_CMD "${RUN_ARGS[@]}" || run_rc=$?

# Best-effort S3 sync (job has AWS_* secrets but no aws CLI -> uvx). A sync
# failure never fails the run; outputs still persist on weka at $RUN_DIR.
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
