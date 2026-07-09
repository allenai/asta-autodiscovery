#!/usr/bin/env bash
#
# Interactive-session bootstrap: install Claude Code (persisted to a durable
# location so it survives an ephemeral session FS) and set up the project
# Python env.
#
# Usage (source it so the exports land in your shell):
#   source scripts/vllm/session_startup.sh
#
# Auth: pass your key into the session rather than hardcoding it here, e.g.
#   beaker session create --secret-env ANTHROPIC_API_KEY=<your-beaker-secret> ...
# then just run `claude`.
#
# NOTE: the Python-env section below is a template. Point WEKA_HOME at your own
# persistent storage and adapt the install step to how this project is packaged.

set -uo pipefail

# --- persistent, durable locations (override WEKA_HOME for your workspace) -----
WEKA_HOME="${WEKA_HOME:-$HOME}"                                      # persistent storage root
export CLAUDE_CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$WEKA_HOME/.claude}"   # login/config persists here
CLAUDE_INSTALL_DIR="${CLAUDE_INSTALL_DIR:-$WEKA_HOME/.local/bin}"     # the `claude` binary lives here
export PATH="$CLAUDE_INSTALL_DIR:$HOME/.local/bin:$PATH"

# --- install Claude Code (native binary; no Node/sudo required) ---------------
if ! command -v claude >/dev/null 2>&1; then
    echo "[startup] installing Claude Code -> $CLAUDE_INSTALL_DIR"
    mkdir -p "$CLAUDE_INSTALL_DIR"
    # Native installer drops a standalone binary; point it at the durable dir.
    export CLAUDE_INSTALL_DIR
    curl -fsSL https://claude.ai/install.sh | bash
else
    echo "[startup] claude already on PATH: $(command -v claude)"
fi
command -v claude >/dev/null 2>&1 && claude --version || echo "[startup] WARN: claude not found on PATH"
[ -n "${ANTHROPIC_API_KEY:-}" ] || echo "[startup] WARN: ANTHROPIC_API_KEY unset — set it or run 'claude' to log in"

# --- project Python env -------------------------------------------------------
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
if [ ! -x .venv/bin/python ]; then
    echo "[startup] creating project venv (.venv) with uv"
    uv venv .venv --python 3.11
    uv pip install --python .venv/bin/python -e .
fi

# Repo root on PYTHONPATH so relative-path project imports resolve.
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"
# Activate the venv for the current shell (only meaningful when sourced).
# shellcheck disable=SC1091
source .venv/bin/activate 2>/dev/null || true

echo "[startup] ready. python=$(command -v python)  claude=$(command -v claude || echo missing)"
