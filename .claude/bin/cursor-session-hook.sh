#!/usr/bin/env bash
# Cursor `sessionStart` hook for np.
#
# Cursor's session hook is SYNCHRONOUS with a timeout and expects structured
# JSON on stdout — where Claude Code's SessionStart is async and treats raw
# stdout as context. So this wrapper splits bootstrap.sh in two:
#
#   slow half  -> `bootstrap.sh --session-bg`, double-forked and detached
#                 (pip, pipx, `ccc index` — minutes; never on the critical path)
#   fast half  -> `bootstrap.sh --drift-only` under a hard `timeout`, whose
#                 prose becomes `additional_context`. On timeout we fall back to
#                 the previous session's cached text: drift is then reported one
#                 session late, which is the right trade against blocking.
#
# Output contract (Cursor sessionStart):
#   {"env": {...}, "additional_context": "..."}
# `env` is handed to every later hook in the session. ALWAYS exits 0.
#
# Inert under Claude Code — nothing there invokes it.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${NP_PLUGIN_ROOT:-${CURSOR_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$(dirname "$SCRIPT_DIR")}}}"
DATA="${NP_PLUGIN_DATA:-${CLAUDE_PLUGIN_DATA:-$HOME/.np-poc-data}}"
PROJ="${CURSOR_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$PWD}}"
# Creation default only — the probe still finds a base any editor created,
# so a Cursor dev joining a Claude-initialized repo shares it.
HOME_DEFAULT="${NP_HOME_DEFAULT:-.cursor}"
INIT_CMD="${NP_INIT_CMD:-/np-init}"
DRIFT_BUDGET="${NP_DRIFT_TIMEOUT:-8}"
PY="$SCRIPT_DIR/_py.sh"
CACHE="$DATA/drift-cache.txt"

mkdir -p "$DATA" 2>/dev/null || true
IN="$(cat 2>/dev/null || true)"   # {session_id,is_background_agent,composer_mode,…}

# --- 1. slow half: fully detached, survives this hook exiting ---------------
(
  cd "$PROJ" 2>/dev/null &&
  NP_PLUGIN_ROOT="$ROOT" NP_PLUGIN_DATA="$DATA" NP_HOME_DEFAULT="$HOME_DEFAULT" \
  NP_INIT_CMD="$INIT_CMD" \
  nohup bash "$ROOT/bin/bootstrap.sh" --session-bg >/dev/null 2>&1 &
) >/dev/null 2>&1 || true

# --- 2. fast half: hard-bounded, cached ------------------------------------
DRIFT=""
if command -v timeout >/dev/null 2>&1; then
  DRIFT="$(cd "$PROJ" 2>/dev/null &&
    NP_PLUGIN_ROOT="$ROOT" NP_PLUGIN_DATA="$DATA" NP_HOME_DEFAULT="$HOME_DEFAULT" \
    NP_INIT_CMD="$INIT_CMD" \
    timeout "$DRIFT_BUDGET" bash "$ROOT/bin/bootstrap.sh" --drift-only 2>/dev/null)"
  rc=$?
else
  # macOS without coreutils has no `timeout`; the drift check is bounded
  # internally (detect_stack.py runs with its own 60s subprocess timeout).
  DRIFT="$(cd "$PROJ" 2>/dev/null &&
    NP_PLUGIN_ROOT="$ROOT" NP_PLUGIN_DATA="$DATA" NP_HOME_DEFAULT="$HOME_DEFAULT" \
    NP_INIT_CMD="$INIT_CMD" \
    bash "$ROOT/bin/bootstrap.sh" --drift-only 2>/dev/null)"
  rc=$?
fi
if [ -n "$DRIFT" ]; then
  printf '%s' "$DRIFT" >"$CACHE" 2>/dev/null || true
elif [ "$rc" -eq 124 ] && [ -f "$CACHE" ]; then
  DRIFT="$(cat "$CACHE" 2>/dev/null || true)"
fi

# --- 3. is this a headless run? --------------------------------------------
BG="$(printf '%s' "$IN" | "$PY" -c \
  'import json,sys
try: print("1" if json.load(sys.stdin).get("is_background_agent") else "0")
except Exception: print("0")' 2>/dev/null || echo 0)"

# --- 4. emit the JSON ------------------------------------------------------
HOME_DIR="$(cd "$PROJ" 2>/dev/null && for d in .cursor .claude .np; do
  [ -f "$d/np.config.json" ] && { echo "$d"; break; }; done)"
HOME_DIR="${HOME_DIR:-$HOME_DEFAULT}"
CTX="np harness active. Plugin runtime root: $ROOT — that is what \`\${CURSOR_PLUGIN_ROOT}\` means in np skills and agents. Project config: $HOME_DIR/np.config.json; knowledge base: $HOME_DIR/project_context/. Initialize with $INIT_CMD."
if [ "$BG" = "1" ]; then
  CTX="$CTX

[np-noninteractive] This is a background/headless run. For every np human gate, take the np.config.json default, say in one line which default you used, and never stop to ask."
fi
if [ -n "$DRIFT" ]; then
  CTX="$CTX

$DRIFT"
fi

NP_CTX="$CTX" NP_ENV_ROOT="$ROOT" NP_ENV_DATA="$DATA" \
NP_ENV_HOME="$HOME_DEFAULT" NP_ENV_INIT="$INIT_CMD" "$PY" -c '
import json, os
print(json.dumps({
    "env": {
        "NP_PLUGIN_ROOT": os.environ["NP_ENV_ROOT"],
        "NP_PLUGIN_DATA": os.environ["NP_ENV_DATA"],
        "NP_HOME_DEFAULT": os.environ["NP_ENV_HOME"],
        "NP_INIT_CMD": os.environ["NP_ENV_INIT"],
        "NP_HOST": "cursor",
    },
    "additional_context": os.environ["NP_CTX"],
}))' 2>/dev/null || printf '{"env":{},"additional_context":""}'

exit 0
