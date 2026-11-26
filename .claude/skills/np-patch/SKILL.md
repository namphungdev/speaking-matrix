---
name: np-patch
description: Lightweight fix loop for small, obvious changes (syntax errors, one-liner bugs, tiny well-understood edits) — mint a minimal run dir, load cached context, edit up to 3 files directly in the working tree behind the conventions pre-write checklist, gate on np_build_verify plus scoped existing tests, run the scoped adversarial review, record patch-result.json for the context-updater. Escalates to /np-plan the moment a scope guardrail is hit. Minutes, not the full plan→implement pipeline.
---

# np-patch — minutes-scale fix, guardrailed

Direct-edit exception: unlike `np-implement`, YOU edit the files — no orchestrator, no plan document, no approval gate, no model question. The guardrails below are what make that safe; the moment one is hit, escalate. **Escalating IS the success path for an oversized patch — never push through "to finish".**

## Scope guardrails (check BEFORE the first edit and after EVERY edit)

- ≤ 3 files modified. NO new files, deletions, or renames.
- No public API/signature changes, no dependency-manifest changes (`package.json`, `*.csproj`, `requirements.txt`, lockfiles), no DB schema/migrations, no new DI/wiring registrations, no new modules.
- > ~40 changed lines total → treat as a breach.
- One request = one logical fix; "while I'm here" extras are new invocations.

## Step 0 — Preflight

Walk up to the nearest `.claude/np.config.json`; absent → stop: **"np not initialized — run /np-init"**. Read `harness.runs_root` (default `.np-runs`) and `harness.handoff_dirname` (default `.codegen-handoff`). Record `baseline_commit = git rev-parse HEAD`. Dirty tree: do NOT stop and do NOT ask — record the dirty list as `preexisting_dirty`, **as files, not directories** (`git status --porcelain=v1 -uall --no-renames | cut -c4-`); those files are never attributed to this run.

## Step 1 — Mint the run (mirror np-frontend standalone)

`run_id = <YYYYMMDD-HHMMSS>-patch-<slug ≤4 words>`; `mkdir -p` the run dir and handoff dir. Then:

```json
np_write_handoff(handoff_dir, "00-request.json", {
  "agent": "np-patch", "kind": "patch", "task_type": "patch",
  "request": "<full args text>", "run_dir": "<abs run dir>",
  "baseline_commit": "<sha>", "review": false,
  "model": "<models.patch ?? models.implement ?? sonnet>",
  "preexisting_dirty": ["..."]
})
```

No model question — the fallback chain IS the choice; say in one line which tier applies. (You cannot switch the main session's own model; the recorded value is audit metadata and the tier for any sub-agent this run spawns.)

## Step 2 — Load context

Invoke the `load-context` skill with the request summary AND the `handoff_dir` (frame cache write/hit; lesson search always fresh). **Total diagnosis budget: ≤3 searches + ≤5 file reads** — a fix needing more exploration than that is not a patch; escalate, don't grind.

## Step 3 — Diagnose and scope-check

Locate the defect (search before read). State the fix in 2–3 lines: what is wrong, what changes, in which files. Check that statement against the guardrails — a breach here escalates **before anything is touched**.

## Step 4 — Conventions, then edit

Invoke the `conventions` skill once (pre-write checklist). Then edit directly with the Edit tool, one file at a time, running the pre-write checklist before each save and re-checking the guardrails after each file.

## Step 5 — Verify

1. `np_build_verify(target=<touched module's build_target from modules.json>)` for each touched backend stack. Frontend file touched → run that stack's `typecheck` command via Bash from the app root instead (fallback `npx tsc --noEmit`).
2. Existing tests, only if cheap: a test target for the touched module discoverable in ONE `np_list_files`/Glob call → `np_test_run` scoped to it. **Never generate tests.** No target → skip and say so. Failures in untouched areas → report as pre-existing, do not chase.
3. On failure: ≤2 fix attempts, searching `lessons/**` for `ES-*` entries first. Still failing → Step 7 with `status: "failed"`; suggest `/np-plan` or a manual look. Never leave the tree in a state you haven't reported.

## Step 6 — Scoped adversarial review

If `np.config.json` → `review.enabled` is not false: invoke the `np-review` skill (Skill tool name `np-review`; fallback: read `.claude/skills/np-review/SKILL.md`) in pipeline mode — `handoff_dir=<handoff_dir>`, scope = exactly the files you edited, `min_impact = review.patch_min_impact` (default `"medium"`), `agents=[review-bug-hunter, review-security-auditor]`. The verdict is information: report it; never auto-revert.

## Step 7 — Result handoff, then defer-or-run the updater

```json
np_write_handoff(handoff_dir, "patch-result.json", {
  "agent": "np-patch", "status": "success" | "failed" | "escalated",
  "files_modified": ["..."], "build": "passed" | "failed",
  "tests": {"executed": 0, "failed": 0},
  "escalation_reason": "<only when escalated>",
  "context_findings": []
})
```

(`"tests": "skipped"` when Step 5.2 found no target.) Findings only when durable — a novel healed build error → `error-solution`; stale doc/metadata discovered → `correction`. Most patches have none.

Then decide per contract §8.1, exactly like `np-implement` Step 5: **defer** when the args carry `defer_context_update=true` or the dev will run `/np-test <run_id>` next — note the pending count and stop. **Otherwise this is the final stage**: if `context_findings` anywhere in the handoff dir (including `review-findings-ext.json`) are non-empty, spawn the `context-updater` agent with `handoff_dir=<handoff_dir>`; with zero findings, skip and say so.

## Step 7.5 — Record provenance

`np_record_provenance(handoff_dir, "patch")` — the edits are in the working tree and the dev commits them by hand; this is what later proves np made them (git blob hashes into the committed `<np-home>/np-provenance.jsonl`; idempotent; `preexisting_dirty` subtracted). Keep the returned `trailer` and `ledger_rel` for Step 8. Skip only when `np.config.json` → `provenance.enabled` is `false`.

## Escalation (any guardrail breach, any time)

1. STOP editing. Never revert on your own — the tree is the dev's.
2. Write `patch-result.json` with `status: "escalated"`, the reason, and the files already touched — then `np_record_provenance(handoff_dir, "patch")`: the edits stay in the tree whether or not the run continues, so they must stay attributable.
3. Tell the dev: what you found, what already changed (`git diff -- <files>`), and to run **`/np-plan <run_id>`** — np-plan reuses this run dir (request + cached frame + your escalation note) for a real plan.

## Step 8 — Summarize

Files edited + `git diff -- <file…>` pointer (never attribute `preexisting_dirty` files to this run) · build/typecheck + test status · review verdict (quality gate + critical/high counts) · findings applied or pending · next: commit, or `/np-test <run_id>` for the deeper loop · **provenance** — the same block `np-implement` prints in its Step 6 (`Provenance: <N> files recorded → <ledger_rel> — commit it together with the change`, then the `git commit --trailer "<trailer>"` line and its git < 2.32 fallback).

## DO NOT

- Exceed a guardrail "just to finish" — escalate instead.
- Spawn codegen/frontend agents, write a plan file, or ask an approval question — that is `/np-plan` + `/np-implement`.
- Generate new tests, create/delete/rename files, or touch dependency manifests.
- Ask the model question, or stop/ask on a dirty tree.
- Write context entries yourself (contract §8.1 — the `context-updater` sub-agent is the only writer).
