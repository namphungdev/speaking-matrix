---
name: np-feedback
description: Capture ad-hoc dev feedback ("X is outdated, we now do Y") into project context — classify it as a lesson, an error-solution, a business fact, or a modules.json correction, confirm the interpretation when ambiguous, and record it as a dev_confirmed finding that the context-updater sub-agent applies (immediately when standalone, at the end of the run when inside a loop).
---

# np-feedback — Free-Text Feedback into Project Context

You turn one piece of dev feedback into the right durable change in `.claude/project_context/`. The dev is the authority — everything captured here is `dev_confirmed` by definition — but you must capture it precisely, not creatively.

**Division of labour (contract §8.1):** you do the part that needs the dev in the room — reading their meaning, classifying it, asking when it is ambiguous. The `context-updater` sub-agent does the part that needs the knowledge base — finding the entry this touches, superseding vs. refining, editing files, syncing the index. Keeping that second half out of this session is the point: it is long, mechanical, and nothing the conversation needs to remember afterwards.

## Step 0 — Preflight and intake

1. Confirm `.claude/np.config.json` exists. If absent, stop: "np not initialized — run /np-init".
2. The Skill args are the feedback text. If empty, ask: "What's the feedback? (a rule we should remember, a fact that changed, an error+fix worth keeping, or a correction to module metadata)".
3. If the args contain several independent points, split them and run Steps 1–4 per point.

## Step 1 — Do NOT go hunting for the target entry

Resist the urge to `context_list` + `search` the whole knowledge base here. Finding the entry a claim refers to, deciding whether it contradicts or merely refines it, and editing the file is the **`context-updater` sub-agent's** job (contract §8.1) — it does exactly that matching (exact topic, then fuzzy over `project_context/**`) in its own context, and everything it reads to do so would otherwise sit in this conversation for the rest of the session.

Two things only:

1. If the dev **named an entry id** (`LL-…`, `ES-…`, `BC-…`), keep it — it becomes the finding's `supersedes`.
2. If the dev named a `modules.json` field, keep the field path.

Everything else — which entry this touches, whether one exists at all — the updater resolves. Your job is to get the dev's meaning exactly right.

## Step 2 — Classify

| Signal in the feedback | `kind` for the finding |
|---|---|
| New reusable rule/practice | `lesson` |
| An error and how it was fixed | `error-solution` |
| "X is outdated / wrong / we now do Y" | `lesson` — the claim states Y; set `supersedes` when the dev named the old entry's id, else leave `null` and let the updater match X |
| Domain/business fact ("refunds are only partial in market Z") | `business_context` (add a `domain` key) |
| Wrong module metadata (family, capabilities, build target, reference module, placement note) | `correction` |
| Contradicts a documented `conventions.md`/`architecture.md` statement | `lesson` — the updater's guardrail routes `dev_confirmed` findings like this into `## Amendments` on the right file |

## Step 3 — Confirm when ambiguous

Proceed WITHOUT asking only when the classification and the claim's wording are unambiguous. Otherwise present your interpretation and wait:

- Multiple plausible classifications → "I read this as <X>. Alternative: <Y>. Which is it?"
- The replacement rule is unclear ("we don't do X anymore" — and then what?) → confirm the exact new wording before recording it.
- Correction where the intended `modules.json` field is unclear → ask which field and what value.

You do **not** ask which entry to supersede — that is a matching question, and the updater answers it. Ask about meaning, not about targets. When you proceed without asking, state in your report exactly what you assumed.

## Step 4 — Record the findings; the sub-agent applies them

Write one finding per point, verbatim-faithful to the dev's wording — do not embellish, do not broaden. Confidence is always `dev_confirmed` (the dev said it).

```
np_write_handoff(handoff_dir, "feedback-findings.json", {
  "agent": "np-feedback",
  "context_findings": [
    {"topic": "<kebab-key>", "kind": "lesson|error-solution|business_context|correction",
     "claim": "<the feedback, kept as close to verbatim as a claim allows>",
     "evidence": ["dev feedback via /np-feedback, <YYYY-MM-DD>"],
     "supersedes": "<id the dev named, else null>", "confidence": "dev_confirmed",
     "modules": [<named modules>], "domain": "<only for business_context>"}
  ]
})
```

Where `handoff_dir` comes from:

- **Inside a `np-loop` / pipeline run** (the common case — the dev corrects something at a gate): the run's existing handoff dir. Then **defer** — do not spawn the updater; report the recorded findings and let the loop apply them at `stage: done` with everything else.
- **Standalone `/np-feedback`**: this invocation is the whole session, so mint a minimal dir — `run_id` = `<YYYYMMDD-HHMMSS>-feedback`, `handoff_dir = {runs_root}/{run_id}/{handoff_dirname}` from `np.config.json` — write the findings there, then spawn the **`context-updater`** agent with `handoff_dir=<that dir>` and wait for `context-update-report.json`.

The updater does the rest in its own context: matches existing entries, inserts/updates/supersedes, appends `## Amendments` for findings that touch conventions/architecture, makes field-level `modules.json` edits, and runs `context_sync`.

**After the updater (standalone only):** when its report lists `amended`
containing `conventions.md`, refresh the always-on digest so the amendment is
loaded in every session, not only when a skill reads the file:
`python3 ".claude/scripts/harmonize_scan.py" layer --apply`. It rewrites
only np-managed text. In a deferred run, the session hook's harmony check
catches the stale digest next session instead.

## Step 5 — Report

- **Standalone:** read `context-update-report.json` and report exactly what landed — inserted ids + titles, superseded (old id → new id, or "retired"), `modules.json` fields changed, amendments appended, anything `skipped` and why, sync status.
- **Deferred:** report the findings as recorded (topic + kind + claim, one line each), where they are (`feedback-findings.json`), and that the loop applies them at the end of the run.
- Either way: state any assumption you made without asking.

## DO NOT

- Call `context_add_entry` / `context_supersede` / `context_sync`, or edit anything under `project_context/`, yourself — the `context-updater` sub-agent is the only writer (contract §8.1). This skill's value is getting the dev's meaning right, not doing the filing.
- Sweep `context_list` / `search` over the knowledge base to find the target entry — that is the updater's matching step, and doing it here loads the whole vault into the session.
- Guess a supersede id. Either the dev named one or it stays `null`.
- Editorialize the dev's feedback into something broader than what was said.
- Report changes as applied when they were only recorded (deferred mode) — say which it is.
