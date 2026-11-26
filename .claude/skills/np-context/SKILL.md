---
name: np-context
description: Browse and curate the project's knowledge entries — lessons (LL-*), error-solutions (ES-*), and business context (BC-*) in .claude/project_context/. List, inspect, add, and supersede entries via the np-workspace context tools. Use when the user runs /np-context, asks "what lessons do we have", wants to record a lesson/business fact manually, or wants to retire an outdated entry.
---

# np-context — browse & curate knowledge entries

Work against the current project's `.claude/project_context/` through the
**np-workspace MCP tools** (`context_list`, `context_get`,
`context_add_entry`, `context_supersede`, `context_sync`). If the MCP server
is unavailable, fall back to the CLI twin:

```bash
PLUGIN_ROOT="${NP_PLUGIN_ROOT:-${CURSOR_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}}"
python3 "$PLUGIN_ROOT/scripts/ctx_tool.py" <add|supersede|get|list|sync> ...
```

(Dev fallback when neither env var is set: use the grandparent of the
directory this SKILL.md was loaded from — `<plugin-root>/skills/np-context/`.
If you cannot determine it, ask the dev to set `NP_PLUGIN_ROOT`.)

Both refuse with `np not initialized — run /np-init` when the project
has no `.claude/np.config.json`.

**This is the one sanctioned place where the main session writes context
directly** (contract §8.1) — the dev is here explicitly to see and edit
entries, so doing it in front of them is the point. Every *automatic* update
during a pipeline goes through the `context-updater` sub-agent instead, once,
at the end of the run. This skill is also where curation happens: when a
`context-update-report.json` returns a `health` hint (duplicated or foldable
amendments, the same point stated in several places), the fix is a deliberate
pass here — fold amendments into the rules they qualify, supersede what is
stale, delete what is genuinely redundant. There is **no line limit** on these
files; redundancy is a reason to cut, length never is.

## Protocol

1. **Interpret `$ARGUMENTS`** as the requested action; when empty, default to
   a browse: `context_list` (status=active) and render a table
   `id | type | title | updated | modules | tags`, grouped by type. Offer the
   follow-up actions below.

2. **Inspect** (`get <id>` or the user names an entry): `context_get`, render
   the frontmatter fields and full body. For business entries also show the
   domain file and anchor (`business/<domain>.md#<id>`).

3. **Add** (user states a new lesson / error-solution / business fact):
   - Classify the kind: *lesson* = reusable how-to/pitfall; *error-solution* =
     a specific error message → fix pair (title should contain the error
     signature); *business* = domain knowledge (also pick the `domain` file
     stem from `business/_index.md`, default `general`).
   - Draft title (one line), body (concise markdown; for ES entries: Error /
     Cause / Fix sections), kebab-case tags, affected modules. Show the draft
     and get user confirmation if you inferred rather than quoted.
   - Call `context_add_entry` (source: `manual` when dev-stated, `feedback`
     when captured from a correction). Report the minted id and path.

4. **Supersede** (entry is outdated): confirm the target id with the user
   before acting — supersede truncates the body to one line and is not meant
   to be reverted.
   - Replacement exists or is being added now → add the new entry with
     `supersedes: <old-id>` (one call does both sides).
   - Plain retirement → `context_supersede(id)`.
   Never delete entry files; archiving is `/np-reindex --prune`'s job.

5. **Sync**: after any add/supersede batch, run `context_sync` so
   np-code-search reflects the change. Skip only if ccc is unavailable (then
   say so).

6. **Report**: one-line summary per mutation (`added LL-… <title>`,
   `superseded ES-… by LL-…`), plus the sync result.

## Searching entries semantically

For "do we know anything about X?" prefer the np-code-search `search` tool
scoped to context files: `paths: [".claude/project_context/**"]` (lessons
only: `paths: [".claude/project_context/lessons/**"]`). Fall back to
`context_list` + Grep over `project_context/` when the index is unavailable.
