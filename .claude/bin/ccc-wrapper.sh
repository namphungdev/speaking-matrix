#!/usr/bin/env bash
# ccc wrapper (CONTRACT.md §12): ensure the pinned cocoindex-code is
# installed and one-time-configured, then exec `ccc "$@"`.
#
# Used both as a CLI (`ccc-wrapper.sh index`, `ccc-wrapper.sh grep ...`) and
# as the MCP launcher for np-code-search (`ccc-wrapper.sh mcp`) — therefore
# ALL install output goes to stderr so stdout stays clean for the stdio
# protocol. Safe when plugin env vars are unset.
set -euo pipefail

CCC_PIN="cocoindex-code==0.2.37"
CCC_VERSION="0.2.37"
GLOBAL_SETTINGS="$HOME/.cocoindex_code/global_settings.yml"
INIT_CMD="${NP_INIT_CMD:-/np:np-init}"

export PATH="$HOME/.local/bin:$PATH"

# The pinned ccc has NO --version flag (Click rejects it), so detect the
# installed version through the console script's own interpreter — works for
# pipx, uv, and any other install route — with pipx/uv tool listings as
# fallbacks. Keep this in sync with ccc_fresh() in bootstrap.sh.
have_pinned() {
  local ccc_path py v
  ccc_path="$(command -v ccc 2>/dev/null)" || return 1
  py="$(head -n 1 "$ccc_path" 2>/dev/null | sed -n 's/^#!//p' | awk '{print $1}')"
  if [ -n "$py" ] && [ -x "$py" ]; then
    v="$("$py" -c 'import importlib.metadata as m; print(m.version("cocoindex-code"))' 2>/dev/null || true)"
    if [ "$v" = "$CCC_VERSION" ]; then
      return 0
    fi
  fi
  if command -v pipx >/dev/null 2>&1 \
    && pipx list 2>/dev/null | grep -q "cocoindex-code.*$CCC_VERSION"; then
    return 0
  fi
  if command -v uv >/dev/null 2>&1 \
    && uv tool list 2>/dev/null | grep -qF "cocoindex-code v$CCC_VERSION"; then
    return 0
  fi
  return 1
}

# cocoindex-code 0.2.37 refuses EVERY command (index/search/mcp) until
# ~/.cocoindex_code/global_settings.yml exists ("Run `ccc init`"). Create it
# non-interactively when we can; otherwise fail with an actionable message.
# `ccc init` is run from a scratch dir so its project-side effects (a
# .cocoindex_code/settings.yml in cwd) never land in the caller's directory.
ensure_global_settings() {
  [ -f "$GLOBAL_SETTINGS" ] && return 0
  local tmp
  tmp="$(mktemp -d)"
  if [ -n "${NP_CCC_LITELLM_MODEL:-}" ]; then
    echo "[ccc-wrapper] one-time setup: ccc init --litellm-model $NP_CCC_LITELLM_MODEL" >&2
    (cd "$tmp" && ccc init --litellm-model "$NP_CCC_LITELLM_MODEL" --force) 1>&2 </dev/null || true
  else
    # Non-TTY `ccc init` without a model flag succeeds only when the
    # sentence-transformers extra is installed (it then defaults to a local
    # model). Cheap to attempt; silent no-op otherwise.
    (cd "$tmp" && ccc init --force) 1>&2 </dev/null || true
  fi
  rm -rf "$tmp"
  [ -f "$GLOBAL_SETTINGS" ] && return 0
  cat >&2 <<EOF
[ccc-wrapper] ERROR: ccc is installed but not configured — $GLOBAL_SETTINGS
is missing, and cocoindex-code refuses every command without it.
One-time fix (per machine), any of:
  1. run \`ccc init\` in a terminal and pick an embedding provider/model, OR
  2. export NP_CCC_LITELLM_MODEL=<litellm embedding model>
     (e.g. openai/text-embedding-3-small, with its API key exported) and
     re-run — this wrapper will configure it automatically, OR
  3. install local embeddings (no API key, large download):
       pipx install --force 'cocoindex-code[embeddings-local]==$CCC_VERSION'
     then re-run.
$INIT_CMD walks you through this (Step 9).
EOF
  return 1
}

if ! have_pinned; then
  if command -v pipx >/dev/null 2>&1; then
    echo "[ccc-wrapper] installing $CCC_PIN via pipx" >&2
    pipx install --force "$CCC_PIN" 1>&2
  elif command -v uv >/dev/null 2>&1; then
    echo "[ccc-wrapper] installing $CCC_PIN via uv tool" >&2
    uv tool install --force "$CCC_PIN" 1>&2
  else
    echo "[ccc-wrapper] ERROR: neither pipx nor uv found — install one, or run:" >&2
    echo "  pipx install '$CCC_PIN'" >&2
    exit 1
  fi
fi

command -v ccc >/dev/null 2>&1 || {
  echo "[ccc-wrapper] ERROR: ccc still not on PATH after install" >&2
  exit 1
}

# `ccc init` is exactly the command that CREATES the global settings — never
# gate it on itself (np-init Step 9 calls `ccc-wrapper.sh init ...`).
if [ "${1:-}" != "init" ]; then
  ensure_global_settings || exit 1
fi

exec ccc "$@"
