---
name: np-harmonize
description: Bring an already-initialized project in line with the installed np plugin, without re-init or re-indexing. Migrates project_context to the current plugin version (missing baseline rules, config upkeep), finds project rules/skills/memory files that contradict the conventions or claim authority over them and aligns each one automatically, and installs an always-on conventions digest (memory file + Cursor rules + project-skill headers) so conventions hold even when nobody runs a np command. Runs end to end without questions; --ask restores the per-finding gate, --check is a dry run. Use when the user runs /np-harmonize, after updating the plugin, when a [np-drift] notice says conventions are not harmonized, or when generated code ignores the project's conventions.
---

# np-harmonize — one source of truth for conventions, always loaded

The project's `conventions.md` (plus its `## Amendments`) and `architecture.md`
are the source of truth. This skill makes everything else agree with them and
puts a compact digest of them where every session reads it.

Resolve paths:

```bash
PLUGIN_ROOT="${NP_PLUGIN_ROOT:-${CURSOR_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}}"
TARGET_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

Below, `$H …` is shorthand for `python3 "$PLUGIN_ROOT/scripts/harmonize_scan.py" …` —
write the full command with the path spelled out; some shells (zsh) do not
word-split a variable. Keep each call a single command: the plugin's PreToolUse
gate auto-approves exactly this script invoked on its absolute path, so a `cd`
prefix, a `&&` chain or a second command on the same call turns a silent run
into a permission prompt for the developer.

Dev fallback when no env var is set: `PLUGIN_ROOT` is the grandparent of the
directory this SKILL.md was loaded from. Precondition: a `np.config.json` in
the project's np home (`.claude/`, `.cursor/` or `.np/`). If there is none,
stop and tell the user to run `/np-init` — init ends by running this skill.

**Arguments:**

| | |
|---|---|
| none (the normal case) | Runs every step end to end and applies every alignment **without asking the developer anything**. Report at the end. |
| `--ask` | The old behaviour: one gate per finding (protocol below), for a developer who wants to decide case by case. |
| `--check` | Dry run — Steps 1–3 and a report. No writes, no questions. |

Every write is idempotent and only ever touches text between `np:managed`
markers, files marked `np:generated`, pristine generated files, or the exact
rule lines Step 3 decided on. Nothing outside the boundary in Step 6 is ever
written, in any mode.

### Autonomous by default — what you decide, and what you never decide

Run the whole thing yourself. **Do not ask the developer to confirm anything**,
do not pause for approval, and do not treat a quiet run as a reason to skip
work — the developer ran this command to have the project fixed, and git is
their undo.

You decide, on your own: every **a / b / d** finding (Step 3) gets the aligned
wording; missing baseline sections go in; upkeep runs; the always-on layer is
written. The report (Step 6) lists every line you changed, so the review
happens on the diff instead of in a prompt.

You never decide, in any mode: deleting a rule (alignment rewrites, never
removes); editing `lessons/`, `business/`, user-level files, or anything the
installer owns; touching source code. A **c** finding (weak reference module)
switches automatically only on unambiguous evidence — see Step 4 — and is
otherwise reported with the one-line command to switch it.

### Human gate — only under `--ask`

**How:** use the `AskUserQuestion` tool when it is available. When it is not,
ask in prose instead — one question, options as a numbered list, the
recommended one marked `(recommended)` — then **END YOUR TURN and wait**.

**When not to:** skip the gate when the run is genuinely non-interactive, i.e.
ANY of: the session context contains `[np-noninteractive]`;
`np.config.json` → `harness.interactive` is `false`; the invocation text
already answers the question. Then fall back to the default mode above and say
so in one line — a `--ask` run that cannot ask still harmonizes the project.

## Step 1 — Inventory

```bash
$H scan
```

Read the JSON. It gives you: `version` (project vs installed plugin);
`generated` (each project_context file, `pristine` = untouched since
generation, plus per-file-mandate candidates); `baseline` (missing baseline
rule sections and checklist lines); `digest` (recorded vs current hash);
`memory_file`; `surfaces` (every project-owned instruction file — memory
files, rules, project skills/agents/commands, Cursor rules — with candidate
lines); `upkeep`; `reference_modules` (how much of each reference module and
its family siblings was created by the pipeline, from the provenance ledger);
`user_level_report_only`. Plugin-owned vendored files are already excluded —
the installer owns them; never edit them.

Candidates are regex hits in generic categories (`per-file-mandate`,
`authority-claim`, `file-list-layout`, `kind-list-layout`, `doc-comment-rule`).
They are leads, not findings: Step 3 decides — and they are not the whole
search. Code samples inside fenced blocks are skipped, so a hit is always rule
text.

## Step 2 — Migrate project_context to the installed plugin

1. **Baseline rules.** If `baseline.missing_sections` or `missing_checklist`
   is non-empty, run `$H baseline --apply` (inserts the template's sections
   verbatim in template order and records the new hash). When `conventions.md`
   was hand-edited, run `$H baseline --apply --allow-edited` — the insert is
   additive, nothing the developer wrote is rewritten, and the old hash is kept
   exactly like re-init's sidecar rule. Under `--ask`, ask first ("add baseline
   rules <ids>"); otherwise just do it and name the ids in the report.
2. **Upkeep.** Run `$H upkeep --apply` (`.gitattributes` merge rule, the
   ledger index exclude in `np.config.json`). Relay its `warnings` and
   `report_only` lines verbatim — a gitignored ledger needs a `.gitignore`
   negation the developer adds.
3. `lessons/` and `business/` are never touched.

With `--check`, run the same commands without `--apply`, report, and skip
Steps 4–5.

## Step 3 — Find conflicts against the source of truth

Read `conventions.md` (all of it, including `## File Placement` and
`## Amendments`) and `architecture.md`. Then read every surface that has
candidates, and skim the rest of the surfaces for the categories below. Judge
each lead in context; report only real findings. Categories — generic, never a
particular project's wording:

- **a. Conflict** — the file requires something the conventions forbid or
  contradicts a rule: a per-file mandate against B7, a different location than
  `## File Placement`, a different error/logging/constants shape than the rule
  states. Also per-file wording inside `conventions.md`/`architecture.md`
  themselves ("in its own file", "one type per file", "one per file" in a
  placement row) — np-init used to generate it; the kind and location stay,
  the per-file clause goes.
- **b. Authority claim** — text that makes a file outrank `conventions.md`
  ("authoritative", "this is the truth", "wins", `authoritative: true`
  frontmatter). Pointing at the conventions file as the source is fine.
- **c. Weak reference module** — `reference_modules[].reference.pipeline_share`
  is high, or clearly above a sibling's; or the reference's comparable units
  hold far more files than a hand-written sibling's (check with
  `np_list_files`). B7 anchors on the reference, so a fragmented reference
  teaches fragmentation. Propose the sibling with the evidence.
- **d. Restatement or staleness** — a file that restates a rule in its own
  words (it will drift), rule ids that no longer exist, pointers to deleted
  files, a hook or block registered twice.

**Compare rule by rule, not only lead by lead.** For each baseline rule
(B1–B7, and FB1–FB2 when present), find every project rule on the same
subject — constants and literals, secrets, error handling, duplication, dead
code, comments and documentation, file granularity — and check that they
agree. Two shapes are easy to miss because neither says "own file":

- a rule that lays out a unit as a list of file names
  (`{Command.ext, Handler.ext, Validator.ext}`, category `file-list-layout`)
  reads to a planner as one file per member. Align it to name the kinds and
  their folder, and say the file split follows B7. **This is the single most
  common cause of generated code arriving as a folder of near-empty files —
  treat every hit as a finding unless the quoted line already defers to B7.**
- the same shape without extensions: a rule or a `## File Placement` row that
  names three or more artifact kinds for one unit (`<X>Command`, `I<X>Handler`,
  `<X>Handler`, `<X>Validator`, category `kind-list-layout`). Keep the kinds and
  the location; append the file-split clause. These hits live in
  `conventions.md` itself as often as in a project rule file — the generated
  P-rules and placement table are in scope exactly like any other surface.
- a rule that requires documentation on every public member, every
  parameter, or every return value contradicts B6. Align it to "document
  only what the name and signature do not say", unless a toolchain setting
  enforces it (then it is a mandate — cite the setting).

The aligned wording is the same in every case: keep the rule's kinds, naming and
location, and add a clause of the shape *"…; how many files carry these follows
B7 — single-use members live with their consumer."* Never invent a different
split; never delete the rule.

Each finding: file, line, quoted text, category, and the exact edit you
propose. A file can carry several.

## Step 4 — Apply the alignments

Every **a / b / d** finding is aligned. Build one edit list and hand it to the
script — it writes the lines, checks each one is still what the scan saw, and
re-hashes any generated file that was pristine, so a later re-init still
regenerates it in place:

```bash
python3 "$PLUGIN_ROOT/scripts/harmonize_scan.py" align --apply --edits - <<'JSON'
{"edits": [
  {"path": "<project-relative path>", "line": <n>,
   "old": "<the line exactly as the scan quoted it>",
   "new": "<the aligned line>",
   "category": "file-list-layout", "rule": "B7"}
]}
JSON
```

Rules for `new`, every time:

- **Rewrite, never delete.** Keep the rule's id, its kinds, its naming and its
  location; change only the clause that conflicts. A `new` that is empty is
  refused by the script.
- **Replace the conflicting text — do not append a contradiction.** A clause
  bolted onto a surviving file list leaves the planner two instructions and it
  will follow the concrete one. The file list has to go.

  ```
  # BAD — the list still names four files; the clause argues with it
  `Features/<UseCase>/{Command.ext, I<X>Handler.ext, <X>Handler.ext, <X>Validator.ext}`; the file split follows B7
  # GOOD — kinds and folder, then the clause
  `Features/<UseCase>/` holds the command, the handler (with its interface where
  the reference module has one) and the validator; how many files carry these
  follows B7 — single-use members live with their consumer
  ```

- **Keep the line's own syntax intact.** In a markdown table row the clause goes
  *inside* the last cell, before the closing `|` — never after it, which breaks
  the table. In a bullet it stays in the bullet. Preserve leading whitespace,
  list markers and bold ids exactly.
- Per-file clause (`in its own file`, `one type per file`) → drop that clause,
  keep the rest of the sentence.
- Authority claim → drop the claim, keep the rule. Pointing at `conventions.md`
  as the source is fine and stays.
- Restated or stale rule → replace the restatement with a one-line pointer to
  the conventions rule id.
- Doc-comment mandate against B6 → "document only what the name and signature
  do not say", unless a toolchain setting enforces it (then leave it and report
  the setting as the reason).

Re-read each line you changed (`sed -n '<line>p' <file>`) before moving on: it
must still be a sentence, a bullet or a table row of the same shape, and it must
no longer carry the text the finding quoted.

**Writing through the script is the sanctioned path, not a workaround.** It is
what makes the run quiet: hosts treat files under `.claude/` or `.cursor/` as
sensitive and would otherwise ask the developer to approve each Edit. The
script enforces the same boundary the Edit tool would (no plugin-owned files,
no `lessons/`, no `business/`, nothing outside the project) and refuses a line
that changed since the scan. Do not fall back to the Edit tool for these files,
and never widen the edit beyond the lines in your list.

Read the result: `aligned` landed, `already-aligned` was a no-op (an earlier
run did it), `refused` did not land and carries the reason — report every
refusal verbatim, and never retry it by another route.

**Under `--ask`**, show the findings as one table (file:line, category, quote,
proposed edit) and ask per finding first — batch up to four per question —
then align only the approved ones:

| Option | Effect |
|---|---|
| **Align** (recommended for a, b, d) | The edit above. |
| **Keep as project rule** | Leave the file, and append the rule to `conventions.md` `## Amendments` in the updater's shape (`### <YYYY-MM-DD> — <topic>` / `- Claim:` / `- Evidence:` / `- Source: np-harmonize`) — it becomes a deliberate mandate that B7 and the planner respect, and stops being reported. |
| **Skip** | No change; reported again next run. |

"The existing code already follows the old rule" is never a reason to keep one:
these rules govern files written from now on, and harmonize never rewrites
existing source. The only rule worth keeping is one that encodes a constraint
the baseline does not know about — a toolchain or framework requirement — and
in the default mode you keep it by **not** aligning it and saying which setting
enforces it, not by asking.

**Category c (weak reference module).** Switch it automatically only when the
evidence is unambiguous: the reference's `pipeline_share` is ≥ 0.5 **and** a
same-family sibling has a materially lower share. Then edit
`reference_modules` in `modules.json` and
`layout_families.<family>.reference_module` in `np.config.json` together (one
`align` edit each), and say so in the report with both numbers. Otherwise do
not switch — report the candidate, the shares, and the two fields to change.

## Step 5 — Install the always-on layer

Pick the project skills that write or edit source code (from Step 1's
surfaces: skills whose instructions produce code, not review-only or
ops-only ones), then:

```bash
$H layer --apply --skill-header <path/to/SKILL.md> [--skill-header …]
```

This renders the digest from `conventions.md` (CRITICAL/HIGH rules, one line
each, plus amendments and the precedence sentence) and writes it into the
`np:managed` block of the memory file, into `.cursor/rules/np-conventions.mdc`
(always applied) and one glob-scoped rule per stack root when the repo uses
Cursor, and a one-line managed header into each named skill. It records
`digest_hash` and `plugin_version` in `_meta.json` — run it LAST, so the
version stamp means the migration finished.

## Step 6 — Self-check and report

Run `git status --porcelain`. Every changed path must be under the np home,
a memory file, `.cursor/rules/`, a project skill/agent/command or rule file
Step 4 aligned, `.gitattributes`, or `.gitignore`. Revert anything else
and say so.

The report replaces the questions you did not ask, so it has to be enough to
review from. Short, but complete:

- plugin version migrated from → to; baseline sections added;
- **every rule line you changed**, one line each: `file:line — <rule id> <what
  the clause said> → <what it says now>`, plus any `refused` row with its
  reason. The developer reviews this on the diff (`git diff <np home> …`) and
  reverts what they disagree with — say that in one line, with the paths;
- any rule you deliberately left alone because a toolchain enforces it, and
  which setting;
- the reference-module switch when one happened (old → new, both shares), or
  the candidate and the two fields when it did not;
- when any `file-list-layout` / `kind-list-layout` finding was aligned, one line
  on what it changes: the next `/np-plan` states how many new files it adds
  against a comparable unit, and `/np-implement` folds back any file the plan
  did not list;
- files written; user-level files that need the developer's own attention
  (`user_level_report_only` — never edited);
- next step only if needed: `/np-reindex` when the index config changed.

## DO NOT

- Edit plugin-owned files, `lessons/`, `business/`, or user-level files.
- Ask the developer to confirm, approve or choose anything in the default mode — align, write, and report. Questions belong to `--ask`.
- Delete a rule, a section or a file. An alignment rewrites the conflicting clause and keeps everything else.
- Edit a project rule, skill or memory file with the Edit tool — Step 4's `align` is the writer, and it is what keeps the run free of per-file approval prompts.
- Regenerate whole project_context files — that is np-init's re-init.
- Invent rules: a finding must quote a line and name the conventions rule it conflicts with.
- Write project-specific wording into the plugin's own templates.
