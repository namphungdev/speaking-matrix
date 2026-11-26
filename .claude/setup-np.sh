#!/usr/bin/env bash
# One-time, per-machine setup for the np harness committed in this repo.
# Run once after cloning (Git Bash on Windows, or any bash on macOS/Linux):
#
#   bash .claude/setup-np.sh
#
# Installs the pinned code-search tool with local embeddings (no API key) and
# configures it, then pre-warms the np-workspace venv. Idempotent: safe to re-run.
set -euo pipefail

CCC_VERSION="0.2.37"
CCC_SPEC="cocoindex-code[embeddings-local]==${CCC_VERSION}"
GLOBAL_SETTINGS="$HOME/.cocoindex_code/global_settings.yml"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

say()  { echo "[np-setup] $*"; }
fail() { echo "[np-setup] ERROR: $*" >&2; exit 1; }

# 1. Python 3.11+
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1 \
     && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || fail "Python 3.11+ not found on PATH — install it first (https://www.python.org/downloads/)."
say "python: $("$PY" --version 2>&1)"

# 2. pipx
if ! command -v pipx >/dev/null 2>&1; then
  say "pipx not found — installing it with pip --user"
  "$PY" -m pip install --user --quiet pipx
  "$PY" -m pipx ensurepath >/dev/null || true
  PIPX=("$PY" -m pipx)
else
  PIPX=(pipx)
fi

# 3. cocoindex-code with local embeddings (large download: PyTorch)
# (Checked through pipx, not the ccc launcher: on Windows ccc is an .exe that is
#  locked while the index daemon runs, so a needless reinstall would fail.)
if "${PIPX[@]}" list --short 2>/dev/null | grep -qF "cocoindex-code $CCC_VERSION" \
   && "${PIPX[@]}" runpip cocoindex-code show sentence-transformers >/dev/null 2>&1; then
  say "cocoindex-code $CCC_VERSION (local embeddings) already installed"
else
  say "installing $CCC_SPEC — this downloads PyTorch, it can take several minutes"
  "${PIPX[@]}" install --force "$CCC_SPEC"
fi
export PATH="$HOME/.local/bin:$PATH"
command -v ccc >/dev/null 2>&1 \
  || fail "ccc is installed but not on PATH — run \`pipx ensurepath\`, reopen the terminal, re-run this script."

# 4. One-time embedding choice: local sentence-transformers model, no API key
if [ -f "$GLOBAL_SETTINGS" ]; then
  say "embedding settings already present: $GLOBAL_SETTINGS"
else
  tmp="$(mktemp -d)"
  (cd "$tmp" && ccc init --force </dev/null) >/dev/null 2>&1 || true
  rm -rf "$tmp"
  [ -f "$GLOBAL_SETTINGS" ] || fail "ccc init did not create $GLOBAL_SETTINGS — run \`ccc init\` manually and pick a local model."
  say "embedding settings created: $GLOBAL_SETTINGS"
fi

# 5. Pre-warm the np-workspace venv so the first Claude session does not race it
say "pre-warming the np-workspace venv"
NP_INIT_CMD="/np-init" bash "$REPO_ROOT/.claude/bin/bootstrap.sh" --quiet || \
  say "bootstrap reported a problem — see ~/.np-poc-data/bootstrap.log (the first Claude session retries it)"

say "done. Open Claude Code in $REPO_ROOT and use /np-plan, /np-patch, /np-implement, …"
say "Do NOT run /np-init (already initialized); the code index builds itself in the background."
