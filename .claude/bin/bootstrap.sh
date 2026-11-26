#!/usr/bin/env bash
# np plugin bootstrap (CONTRACT.md §11-12).
#
# Builds/refreshes the Python venv in $CLAUDE_PLUGIN_DATA and installs the
# pinned cocoindex-code via pipx (fallback: uv tool install).
#
# Usage:
#   bootstrap.sh            full bootstrap (venv + ccc), verbose
#   bootstrap.sh --check    report-only: exit 0 when everything is fresh,
#                           exit 1 when a bootstrap is needed (no changes)
#   bootstrap.sh --quiet    full bootstrap, output to $DATA_DIR/bootstrap.log
#   bootstrap.sh --session  SessionStart hook: bootstrap if stale, kick a
#                           background incremental `ccc index` when the cwd is
#                           inside an initialized project, warn (stderr) when
#                           the managed memory-file block markers are missing.
#                           ALWAYS exits 0 — never blocks the session.
#   bootstrap.sh --session-bg
#                           the SLOW half of --session (venv repair, background
#                           ccc install + index) with NO stdout. For hosts whose
#                           session hook is synchronous; pair with --drift-only.
#   bootstrap.sh --drift-only
#                           the FAST half of --session: managed-block check and
#                           context-drift check only, prose on stdout.
#
# Env:
#   NP_PLUGIN_ROOT     plugin dir  (aliases: CURSOR_PLUGIN_ROOT,
#                       CLAUDE_PLUGIN_ROOT; dev fallback: parent of script dir)
#   NP_PLUGIN_DATA     data dir    (alias: CLAUDE_PLUGIN_DATA;
#                       dev fallback: ~/.np-poc-data)
#   NP_HOME            force the project home dirname (.claude|.cursor|.np);
#                       unset = probe in that order
#   NP_HOME_DEFAULT    dirname to CREATE when a project has none yet
#                       (Cursor installs set .cursor; default .claude)
#   NP_INIT_CMD        the init slash command shown in messages
#                       (default: /np:np-init; Cursor installs: /np-init)
#   NP_SKIP_CCC=1      skip the ccc install step (used by np-mcp.sh)
#   NP_NO_DRIFT=1      session_main skips the managed-block/drift/harmony checks
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${NP_PLUGIN_ROOT:-${CURSOR_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-$(dirname "$SCRIPT_DIR")}}}"
DATA_DIR="${NP_PLUGIN_DATA:-${CLAUDE_PLUGIN_DATA:-$HOME/.np-poc-data}}"
INIT_CMD="${NP_INIT_CMD:-/np:np-init}"
# Local installs and Cursor spell commands /np-<name>; the plugin host /np:<name>.
if [ "$INIT_CMD" = "/np-init" ]; then HARMONIZE_CMD="/np-harmonize"; else HARMONIZE_CMD="/np:harmonize"; fi
VENV="$DATA_DIR/venv"
REQ="$PLUGIN_ROOT/mcp/requirements.txt"
HASH_FILE="$DATA_DIR/requirements.sha256"
CCC_PIN="cocoindex-code==0.2.37"
CCC_VERSION="0.2.37"
GLOBAL_SETTINGS="$HOME/.cocoindex_code/global_settings.yml"
MODE="${1:-}"

export PATH="$HOME/.local/bin:$PATH"

# Portability: Windows venvs use Scripts/python.exe; Git Bash often has
# `python` but not `python3`.
PYBIN="$(command -v python3 || command -v python || echo python3)"
venv_py() {
  if [ -x "$VENV/bin/python" ]; then echo "$VENV/bin/python";
  elif [ -x "$VENV/Scripts/python.exe" ]; then echo "$VENV/Scripts/python.exe";
  else echo ""; fi
}

log() {
  if [ "$MODE" = "--quiet" ] || [ "$MODE" = "--session" ]; then
    mkdir -p "$DATA_DIR"
    echo "[np-bootstrap] $*" >>"$DATA_DIR/bootstrap.log" 2>/dev/null || true
  else
    echo "[np-bootstrap] $*"
  fi
}
warn() { echo "[np-bootstrap] WARN: $*" >&2; }

req_hash() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$REQ" | awk '{print $1}'
  else
    sha256sum "$REQ" | awk '{print $1}'
  fi
}

venv_fresh() {
  [ -n "$(venv_py)" ] || return 1
  [ -f "$HASH_FILE" ] || return 1
  [ -f "$REQ" ] || return 1
  [ "$(cat "$HASH_FILE")" = "$(req_hash)" ] || return 1
  return 0
}

# The pinned ccc has NO --version flag (Click rejects it), so detect the
# installed version through the console script's own interpreter — works for
# pipx, uv, and any other install route — with pipx/uv tool listings as
# fallbacks. Keep this in sync with have_pinned() in ccc-wrapper.sh.
ccc_fresh() {
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

# Fail-closed: the requirements hash is written ONLY after pip succeeded and
# the venv can actually import its deps — a transient pip failure must leave
# venv_fresh() false so the next run repairs it (every `|| return 1` is
# explicit because callers use `build_venv || warn`, which suspends set -e
# inside the function).
build_venv() {
  [ -f "$REQ" ] || { warn "requirements.txt not found at $REQ"; return 1; }
  mkdir -p "$DATA_DIR"
  log "building venv at $VENV"
  rm -f "$HASH_FILE"
  "$PYBIN" -m venv "$VENV" || { warn "$PYBIN -m venv failed"; return 1; }
  local VPY; VPY="$(venv_py)"
  [ -n "$VPY" ] || { warn "venv python not found after creation"; return 1; }
  "$VPY" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
  "$VPY" -m pip install --quiet -r "$REQ" \
    || { warn "pip install -r requirements.txt failed — venv left stale for retry"; return 1; }
  "$VPY" -c 'import mcp, yaml' >/dev/null 2>&1 \
    || { warn "venv sanity import (mcp, yaml) failed — venv left stale for retry"; return 1; }
  req_hash >"$HASH_FILE" || return 1
  log "venv ready"
}

# Does this machine's ccc config ask for LOCAL (sentence-transformers)
# embeddings? Then the plain wheel is not enough — the extra must be installed
# or every `ccc index` dies with "No module named 'sentence_transformers'".
wants_local_embeddings() {
  [ -f "$GLOBAL_SETTINGS" ] || return 1
  grep -qi "sentence[-_]transformers" "$GLOBAL_SETTINGS" 2>/dev/null
}

# The pinned spec to install: with the embeddings-local extra when the config
# needs it (heavy: pulls PyTorch), plain otherwise.
ccc_spec() {
  if wants_local_embeddings; then
    echo "cocoindex-code[embeddings-local]==$CCC_VERSION"
  else
    echo "$CCC_PIN"
  fi
}

# ccc present at the right version AND able to satisfy the configured
# embedding provider.
ccc_usable() {
  ccc_fresh || return 1
  wants_local_embeddings || return 0
  local ccc_path py
  ccc_path="$(command -v ccc 2>/dev/null)" || return 1
  py="$(head -n 1 "$ccc_path" 2>/dev/null | sed -n 's/^#!//p' | awk '{print $1}')"
  [ -n "$py" ] && [ -x "$py" ] || return 0   # can't probe → don't churn
  "$py" -c 'import sentence_transformers' >/dev/null 2>&1
}

install_ccc() {
  if ccc_usable; then
    log "ccc $CCC_VERSION already installed"
    return 0
  fi
  local spec; spec="$(ccc_spec)"
  if ccc_fresh; then
    log "ccc $CCC_VERSION installed but missing local-embedding support — reinstalling as $spec"
  fi
  if command -v pipx >/dev/null 2>&1; then
    log "installing $spec via pipx"
    pipx install --force "$spec" >>"$DATA_DIR/bootstrap.log" 2>&1 \
      || { warn "pipx install $spec failed (see $DATA_DIR/bootstrap.log)"; return 1; }
  elif command -v uv >/dev/null 2>&1; then
    log "installing $spec via uv tool"
    uv tool install --force "$spec" >>"$DATA_DIR/bootstrap.log" 2>&1 \
      || { warn "uv tool install $spec failed"; return 1; }
  else
    warn "neither pipx nor uv found — cannot install $spec (code search disabled)"
    return 1
  fi
  return 0
}

# Host home dirs that may hold np.config.json, in probe order. Kept in sync
# with context_store.NP_HOME_CANDIDATES.
np_home_names() {
  if [ -n "${NP_HOME:-}" ]; then echo "$NP_HOME"; else echo ".cursor .claude .np"; fi
}

find_project_root() {
  local d="$PWD" home
  while [ "$d" != "/" ]; do
    for home in $(np_home_names); do
      if [ -f "$d/$home/np.config.json" ]; then
        echo "$d"
        return 0
      fi
    done
    d="$(dirname "$d")"
  done
  return 1
}

# The initialized home dir inside a project root. An existing base always
# wins, whichever editor created it; only an uninitialized project falls back
# to this host's creation default (NP_HOME_DEFAULT).
np_home_dir() {
  local root="$1" home
  for home in $(np_home_names); do
    if [ -f "$root/$home/np.config.json" ]; then
      echo "$root/$home"
      return 0
    fi
  done
  echo "$root/${NP_HOME:-${NP_HOME_DEFAULT:-.claude}}"
  return 1
}

check_managed_block() {
  # warn when no memory file carries the np managed-block markers.
  # AGENTS.md is Cursor's plain-markdown memory file; CLAUDE.md is Claude
  # Code's. Either satisfies the check — a repo needs only the one its host
  # reads, and a mixed-tool repo usually has both.
  local root="$1" f found=1
  for f in "$(np_home_dir "$root" 2>/dev/null)/CLAUDE.md" \
           "$root/CLAUDE.md" "$root/AGENTS.md"; do
    if [ -f "$f" ] && grep -q "np:managed:start" "$f" 2>/dev/null; then
      found=0
    fi
  done
  if [ "$found" -ne 0 ]; then
    warn "managed memory-file block markers missing in $root — re-run $INIT_CMD to restore"
  fi
}

check_context_drift() {
  # Cheap structural-drift detector: compare the deterministic scan against
  # modules.json and RECOMMEND a re-init when the repo grew modules/stacks the
  # context doesn't know. Warn-only — re-init has a mandatory dev gate and is
  # never run automatically. Fail-open: any error here is silent.
  local root="$1" drift home modules
  home="$(np_home_dir "$root")" || return 0
  modules="$home/project_context/modules.json"
  [ -f "$modules" ] || return 0
  [ -f "$PLUGIN_ROOT/scripts/detect_stack.py" ] || return 0
  drift="$("$PYBIN" - "$root" "$PLUGIN_ROOT/scripts/detect_stack.py" "$modules" <<'PYEOF' 2>/dev/null || true
import json, subprocess, sys
root, detector, modules = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    scan = json.loads(subprocess.run(
        [sys.executable, detector, root], capture_output=True, text=True, timeout=60).stdout)
    known = json.load(open(modules))
    known_paths = {m.get("path", "").rstrip("/") for m in known.get("modules", [])}
    cand = {c.get("path", "").rstrip("/") for c in scan.get("module_candidates", [])
            if not c.get("signals", {}).get("is_test_project")}
    def covered(p):
        # known exactly, or a parent/child of a known module (workspace roots
        # like `frontend/` whose apps are the recorded modules are not drift)
        return (p in known_paths
                or any(k.startswith(p + "/") or p.startswith(k + "/") for k in known_paths))
    new = sorted(p for p in cand if p and p != "." and not covered(p))
    if new:
        mods = ", ".join(new[:4]) + ("…" if len(new) > 4 else "")
        print(f"{len(new)} module(s) on disk are not in modules.json: {mods}")
except Exception:
    pass
PYEOF
)"
  if [ -n "$drift" ]; then
    # Emit a directive INTO the session context (stdout): the assistant must
    # offer the developer a choice, never auto-run the re-init.
    cat <<EOF
[np-drift] Project context is STALE: $drift
ASSISTANT INSTRUCTION — at the start of this session, before other work, ask the
developer "np detected new modules the project context doesn't know. Re-initialize
now?" — with the AskUserQuestion tool where it exists, otherwise as a numbered prose
question. Then END YOUR TURN and wait. Options:
  1. "Re-init now (recommended)" — run $INIT_CMD immediately (hash-guarded:
     hand-edited files get .new.md sidecars; lessons/ and business/ are never touched).
  2. "Not now" — continue without re-init and do not ask again this session.
Never run the re-init without the developer choosing option 1.
EOF
  fi
  return 0
}

check_harmony() {
  # Recommend harmonize when the project lags the installed plugin (its
  # project_context was migrated by an older version) or the always-on
  # conventions digest no longer matches conventions.md. Warn-only, fail-open.
  local root="$1" home reason
  home="$(np_home_dir "$root")" || return 0
  [ -f "$home/project_context/_meta.json" ] || return 0
  [ -f "$PLUGIN_ROOT/scripts/harmonize_scan.py" ] || return 0
  reason="$("$PYBIN" - "$root" "$home" "$PLUGIN_ROOT" <<'PYEOF' 2>/dev/null || true
import json, subprocess, sys
from pathlib import Path
root, home, plugin = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
try:
    meta = json.loads((home / "project_context" / "_meta.json").read_text(encoding="utf-8"))
    current = None
    for m in (".claude-plugin/plugin.json", ".cursor-plugin/plugin.json"):
        if (plugin / m).is_file():
            current = json.loads((plugin / m).read_text(encoding="utf-8")).get("version")
            break
    have = str(meta.get("plugin_version") or "").replace("np/", "")
    out = []
    if current and have != current:
        out.append(f"project context was migrated by plugin {have or 'unknown'}, installed plugin is {current}")
    digest = subprocess.run([sys.executable, str(plugin / "scripts" / "harmonize_scan.py"),
                             "digest", "--hash", "--root", root],
                            capture_output=True, text=True, timeout=60).stdout.strip()
    if digest.startswith("sha256:") and meta.get("digest_hash") != digest:
        out.append("the always-on conventions digest is missing or out of date")
    print("; ".join(out))
except Exception:
    pass
PYEOF
)"
  if [ -n "$reason" ]; then
    cat <<HARMONY
[np-drift] Conventions are not harmonized: $reason.
ASSISTANT INSTRUCTION — at the start of this session, before other work, ask the
developer "np's conventions are out of date for this repo. Harmonize now?" — with
the AskUserQuestion tool where it exists, otherwise as a numbered prose question.
Then END YOUR TURN and wait. Options:
  1. "Harmonize now (recommended)" — run $HARMONIZE_CMD (it runs end to end without
     further questions, aligns the conflicting rule lines and reports every one; no
     re-index, no source file touched, git is the undo).
  2. "Not now" — continue and do not ask again this session.
Never run it without the developer choosing option 1.
HARMONY
  fi
  return 0
}

session_main() {
  mkdir -p "$DATA_DIR" 2>/dev/null || true
  if ! venv_fresh; then
    build_venv || warn "venv bootstrap failed — np-workspace MCP may not start"
  fi
  if [ "${NP_SKIP_CCC:-0}" != "1" ] && ! ccc_fresh; then
    # pipx/uv install can take minutes — never run it in the session's
    # critical path. Double-fork so the install survives this hook exiting;
    # ccc-wrapper.sh retries at MCP startup if it is still mid-flight.
    log "ccc missing/stale — installing $CCC_PIN in the background (see $DATA_DIR/bootstrap.log)"
    ( install_ccc >>"$DATA_DIR/bootstrap.log" 2>&1 & ) || true
  fi
  local root
  if root="$(find_project_root)"; then
    # --session-bg sets NP_NO_DRIFT=1: the host runs these two checks
    # separately (--drift-only) because its hook needs prose on a clean stdout.
    if [ "${NP_NO_DRIFT:-0}" != "1" ]; then
      check_managed_block "$root"
      check_context_drift "$root"
      check_harmony "$root"
    fi
    if ! command -v ccc >/dev/null 2>&1; then
      log "ccc not on PATH yet — skipping incremental index this session"
    elif [ ! -f "$HOME/.cocoindex_code/global_settings.yml" ]; then
      # ccc refuses every command until its one-time `ccc init` ran — a
      # background index would fail silently into index.log every session.
      log "ccc embedding settings missing — skipping background index"
      warn "code search is unconfigured: run \`ccc init\` once (or $INIT_CMD Step 9, or set NP_CCC_LITELLM_MODEL) — see README Troubleshooting"
    elif ! ccc_usable; then
      # e.g. config says sentence-transformers but the plain wheel is installed:
      # every index would die into index.log unnoticed. Say so, don't run it.
      log "ccc cannot satisfy the configured embedding provider — skipping background index"
      warn "code search is broken: ccc is installed without local-embedding support while
      ~/.cocoindex_code/global_settings.yml asks for sentence-transformers. Fix once with:
      pipx install --force 'cocoindex-code[embeddings-local]==$CCC_VERSION'"
    else
      log "starting background ccc index in $root"
      (cd "$root" && nohup ccc index >>"$DATA_DIR/index.log" 2>&1 &) || true
      # surface a previous silent failure (the index runs detached, so its
      # error would otherwise only ever land in index.log)
      if [ -f "$DATA_DIR/index.log" ] && tail -3 "$DATA_DIR/index.log" 2>/dev/null | grep -qi "Indexing failed"; then
        warn "last code-index run FAILED — see $DATA_DIR/index.log: $(tail -1 "$DATA_DIR/index.log")"
      fi
    fi
  fi
}

case "$MODE" in
  --check)
    status=0
    if venv_fresh; then
      echo "[np-bootstrap] venv: fresh ($VENV)"
    else
      echo "[np-bootstrap] venv: MISSING or stale ($VENV)"
      status=1
    fi
    if ccc_usable; then
      echo "[np-bootstrap] ccc: $CCC_VERSION available"
    elif ccc_fresh; then
      echo "[np-bootstrap] ccc: $CCC_VERSION present but WITHOUT local-embedding support"
      echo "[np-bootstrap]      (config asks for sentence-transformers — reinstall as"
      echo "[np-bootstrap]      'cocoindex-code[embeddings-local]==$CCC_VERSION'; indexing fails otherwise)"
      status=1
    else
      echo "[np-bootstrap] ccc: MISSING or wrong version (want $CCC_VERSION)"
      status=1
    fi
    # Informational only (does not affect exit status): the one-time
    # embedding setup is a dev decision — np-init Step 9 walks through it.
    if [ -f "$HOME/.cocoindex_code/global_settings.yml" ]; then
      echo "[np-bootstrap] ccc embedding settings: configured"
    else
      echo "[np-bootstrap] ccc embedding settings: MISSING — one-time \`ccc init\` needed (np-init Step 9 handles this)"
    fi
    exit "$status"
    ;;
  --session)
    session_main || true
    exit 0
    ;;
  --session-bg)
    # The slow half, for hosts with a synchronous session hook. Everything
    # that can take minutes (pip, pipx, ccc index); NOTHING on stdout, which
    # the caller reserves for its own JSON protocol.
    mkdir -p "$DATA_DIR" 2>/dev/null || true
    NP_NO_DRIFT=1 session_main >/dev/null 2>>"$DATA_DIR/bootstrap.log" || true
    exit 0
    ;;
  --drift-only)
    # The fast half: no installs, no index — just the two checks whose output
    # belongs in the model's context. Prose on stdout, always exit 0.
    root="$(find_project_root)" || exit 0
    check_managed_block "$root" || true
    check_context_drift "$root" || true
    check_harmony "$root" || true
    exit 0
    ;;
  ""|--quiet)
    mkdir -p "$DATA_DIR"
    if venv_fresh; then
      log "venv fresh — skipping"
    else
      build_venv
    fi
    if [ "${NP_SKIP_CCC:-0}" != "1" ]; then
      install_ccc || true
    fi
    log "bootstrap complete"
    ;;
  *)
    echo "usage: bootstrap.sh [--check|--quiet|--session|--session-bg|--drift-only]" >&2
    exit 2
    ;;
esac
