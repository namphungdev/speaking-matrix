---
name: np-reindex
description: Re-run the ccc code index for the current np-initialized project. With --prune, first archive lessons superseded more than 30 days ago (moved to lessons/_archive/, which is excluded from the index). Use when the user runs /np-reindex, after large refactors or branch switches, or when np-code-search results look stale.
---

# np-reindex — refresh the code index

Resolve paths:

```bash
PLUGIN_ROOT="${NP_PLUGIN_ROOT:-${CURSOR_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}}"
TARGET_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Dev fallback when neither env var is set: use the grandparent of the
directory this SKILL.md was loaded from (`<plugin-root>/skills/np-reindex/`).
If you cannot determine it, stop and ask the dev to set `NP_PLUGIN_ROOT`.

Precondition: `$TARGET_ROOT/.claude/np.config.json` must exist. If it does
not, stop and tell the user to run `/np-init` first.

## Protocol

1. **Parse arguments** (`$ARGUMENTS`): the only supported flag is `--prune`.
   Optionally `--days <n>` after `--prune` overrides the 30-day default.

2. **Prune (only when `--prune` given)**:

   ```bash
   python3 "$PLUGIN_ROOT/scripts/ctx_tool.py" prune --days "${DAYS:-30}"
   ```

   (`DAYS` = the value from a `--days <n>` argument if the user passed one,
   else 30.)

   This moves lessons whose `status: superseded` and whose `updated` date is
   older than the cutoff into `.claude/project_context/lessons/_archive/`
   (excluded from the index). It prints JSON with the archived ids. Business
   entries are not moved — their bodies are already one-line tombstones inside
   the domain files.

3. **Re-index**:

   ```bash
   cd "$TARGET_ROOT" && bash "$PLUGIN_ROOT/bin/ccc-wrapper.sh" index
   ```

   The wrapper self-installs the pinned `cocoindex-code==0.2.37` if missing.
   On failure, show the error tail and suggest `bash "$PLUGIN_ROOT/bin/bootstrap.sh" --check`.

4. **Report**: entries archived (ids, or "none"), index command output tail
   (files indexed / duration if ccc prints them), and any errors.

Notes:
- The equivalent MCP tool is `context_sync` (np-workspace) — prefer this
  skill when the user asked explicitly, the tool when a pipeline needs a
  refresh mid-run.
- Never edit `.cocoindex_code/` contents by hand; it is derived state and
  gitignored.
