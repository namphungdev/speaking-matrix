#!/usr/bin/env bash
# np-workspace MCP launcher (CONTRACT.md §12).
#
# Self-bootstrapping: when the venv in the data dir is missing or the
# requirements hash is stale, (re)build it via bootstrap.sh, then exec the
# Python MCP server. Registered in the host's MCP config — never point that
# config at the venv python directly (it may not exist yet).
#
# Env (each with a dev-mode fallback, so this runs with nothing set):
#   NP_PLUGIN_ROOT / CURSOR_PLUGIN_ROOT / CLAUDE_PLUGIN_ROOT
#                      -> parent of this script's directory
#   NP_PLUGIN_DATA / CLAUDE_PLUGIN_DATA -> ~/.np-poc-data
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${NP_PLUGIN_ROOT:-${CURSOR_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$(dirname "$SCRIPT_DIR")}}}"
DATA_DIR="${NP_PLUGIN_DATA:-${CLAUDE_PLUGIN_DATA:-$HOME/.np-poc-data}}"
VENV="$DATA_DIR/venv"
REQ="$PLUGIN_ROOT/mcp/requirements.txt"
HASH_FILE="$DATA_DIR/requirements.sha256"

req_hash() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$REQ" | awk '{print $1}'
  else
    sha256sum "$REQ" | awk '{print $1}'
  fi
}

# Windows (Git Bash) venvs use Scripts/python.exe instead of bin/python.
venv_py() {
  if [ -x "$VENV/bin/python" ]; then echo "$VENV/bin/python";
  elif [ -x "$VENV/Scripts/python.exe" ]; then echo "$VENV/Scripts/python.exe";
  else echo ""; fi
}

venv_fresh() {
  [ -n "$(venv_py)" ] || return 1
  [ -f "$HASH_FILE" ] || return 1
  [ -f "$REQ" ] || return 1
  [ "$(cat "$HASH_FILE")" = "$(req_hash)" ] || return 1
  return 0
}

if ! venv_fresh; then
  # venv only — ccc install is the installer's / session hook's job; keep MCP
  # startup fast. All bootstrap output must go to stderr (stdout is the MCP
  # stdio channel).
  NP_SKIP_CCC=1 bash "$SCRIPT_DIR/bootstrap.sh" --quiet 1>&2 || {
    echo "[np-mcp] bootstrap failed — cannot start np-workspace" >&2
    exit 1
  }
fi

exec "$(venv_py)" "$PLUGIN_ROOT/mcp/np_mcp.py"
