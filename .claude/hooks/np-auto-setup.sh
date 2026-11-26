#!/usr/bin/env bash
# SessionStart hook: runs the one-time per-machine np setup (setup-np.sh) in the
# background on a teammate's first session, so nobody has to run it by hand.
# No-op once the machine is configured. Never blocks or fails the session.
set -u

DATA_DIR="${NP_PLUGIN_DATA:-$HOME/.np-poc-data}"
LOG="$DATA_DIR/auto-setup.log"
LOCK="$DATA_DIR/auto-setup.lock"
GLOBAL_SETTINGS="$HOME/.cocoindex_code/global_settings.yml"
SETUP="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}/.claude/setup-np.sh"
RETRY_DELAY_S=60
# A lock older than this belongs to a crashed run, not a live one.
STALE_LOCK_MIN=60

[ -f "$GLOBAL_SETTINGS" ] && exit 0
[ -f "$SETUP" ] || exit 0

mkdir -p "$DATA_DIR" 2>/dev/null || exit 0
find "$LOCK" -maxdepth 0 -mmin +"$STALE_LOCK_MIN" -exec rm -rf {} \; 2>/dev/null
# Several sessions can start at once; only one runs the setup.
mkdir "$LOCK" 2>/dev/null || exit 0
trap 'rm -rf "$LOCK"' EXIT

{
  echo "[np-auto-setup] $(date) first session on this machine — running setup-np.sh"
  # The bootstrap hook may be installing ccc via pipx at the same moment; a
  # failed first attempt is retried once after it has had time to finish.
  bash "$SETUP" || { sleep "$RETRY_DELAY_S"; bash "$SETUP"; } \
    || echo "[np-auto-setup] setup failed — run \`bash .claude/setup-np.sh\` manually to see why"
} >>"$LOG" 2>&1

exit 0
