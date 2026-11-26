---
name: np-loop
description: >-
  Human-gated pipeline driver for one pasted task, composed entirely from the
  existing np component skills. The developer pastes a requirement (or a
  spec-file path); the loop runs load-context plus an intent interview, then
  drives the stages — np-plan, np-implement, np-test,
  code-review-conventions — PAUSING at every stage boundary for an explicit
  go-ahead, with np-feedback available at any gate for durable corrections.
  The approved plan is saved to the repo's plans/ folder. No tickets, no
  polling, no worktrees; everything runs directly on the current branch,
  reviewed via git diff. Sub-commands are the requirement text itself (starts a
  task), status, and advance [run] [note]. Use when the developer runs
  /np-loop with a task, asks to run something through the gated pipeline, or
  wants plan-approval plus stage gates around the np loops.
---

# np-loop — one pasted task, human-gated at every stage

You are a **conductor**, not a coder. The developer gives you the requirement directly (pasted text
or a file path). You interview them for intent, then drive the existing np loops (`np-plan`,
`np-implement`, `np-test`) stage by stage — and you **stop at every stage boundary** until the
developer explicitly says go. You never write feature code yourself, and nothing ever advances on
its own. All work happens **directly on the current branch** (np's in-place contract); `git diff`
is the review surface.

## Sub-commands

| Invocation | What it does |
|---|---|
| `/np-loop "<requirement>"` (or a spec-file path) | Start a new task: intake interview → planning stage → park at the plan gate. |
| `/np-loop status` | Show every tracked task and the gate it is parked at. Read-only. |
| `/np-loop advance [run] [note]` | Developer go-ahead: run the parked task's **next** stage (newest task when `run` omitted). `note` passes extra instruction into the stage. Plain language ("proceed", "run the tests", "implement it") counts too. |

## State

`.claude/np-loop/state.json` (gitignored — add `.claude/np-loop/` to `.gitignore` if missing;
write with the Write tool):

```json
{ "tasks": { "<run_id>": {
    "request": "<pasted requirement, verbatim>",
    "intent": "<interview answers, verbatim>",
    "stage": "planning | implementation | test | review | done",
    "gate": "in_progress | awaiting_go_ahead | blocked",
    "next_action": "implementation",
    "plan_file": "plans/<run_id>.plan.md",
    "baseline_commit": "<HEAD at start>"
} } }
```

Preflight for every invocation: `.claude/np.config.json` must exist — else stop with
"np not initialized — run /np-init".

## Component skills — the loop composes, it never re-implements

Every stage delegates to an existing np skill; the loop adds ONLY the gates and the state between
them. Never inline work a component skill already does.

Model choice is **per stage, asked by the stage itself** — `np-plan` asks which
tier plans (Opus recommended), `np-implement` asks which tier executes (Sonnet
recommended); both remember the answer in `np.config.json` → `models`. Do not
ask again yourself; just relay what each stage reports.

**You own the one context update (contract §8.1).** Pass `defer_context_update=true`
in the args of every stage you invoke, so no stage writes project context mid-run.
The stages record `context_findings` into the shared handoff dir and report a
pending count; you spawn the `context-updater` sub-agent **once**, when the task
reaches `stage: done` (see Done). Rationale: entry matching and file editing is
long, mechanical work that has no business in this conversation, and knowledge
recorded at stage 1 can be contradicted by stage 3 — applying it once at the end
is both cheaper and more correct.

| Stage | Delegates to | Which itself uses |
|---|---|---|
| 0 Intake | `load-context` | np.config.json, architecture summary, active lessons via `search` |
| 1 Planning | `np-plan` | codegen-orchestrator/planner (backend), its own UI plan (frontend), review gate, dev_confirmed findings recorded |
| 2 Implementation | `np-implement` | codegen-planner/implementer/verifier (+ debate agents when flagged), `np-frontend` → frontend-* agents for `kind: frontend` phases, `conventions` before writes, `np_build_verify`, `np-review` (Step 4.5) → review-* adversarial agents, `review-findings-ext.json` |
| 3 Test | `np-test` | codegen-verifier / frontend-verifier, ES lessons via `search`, error-solution findings recorded |
| 4 Review | `code-review-conventions` (working-tree diff) · `np-pr-review` (once a PR exists) | conventions.md rule ids/severities, `review-findings.json` |
| any gate | `np-feedback` — route any durable correction the developer states while reviewing ("X is outdated, we do Y now") | context CRUD + supersede + `context_sync` |
| after big landings | suggest `/np-reindex` (and `/np-context` to curate) when search results looked stale during the task | ccc index |

## Stage 0 · Intake (before any planning — mandatory)

1. Read the requirement (pasted text as-is; if it is a file path, Read the file).
2. Invoke the **`load-context`** skill with a one-line summary of the requirement — the project
   profile and active lessons it surfaces shape your interview questions (e.g. a lesson that
   contradicts the pasted approach is worth asking about). No run exists yet at intake, so this
   one reads the sources directly and caches nothing; Stage 1's `np-plan` creates the run and
   seeds the frame cache that Stages 2–3 then hit.
3. **Interview the developer** — the questions only their domain expertise answers: intended
   approach or a solution they already have in mind? what must this optimize for and what must it
   NOT touch? known landmines or prior art to mirror? Use `AskUserQuestion` for crisp forks — or, where that tool is unavailable,
   a numbered prose question; either way end the turn and wait.
   **Do not proceed until answered.** Record the answers verbatim as `intent`.
4. Warn if `git status --porcelain` shows a dirty tree (recommend commit/stash so the task's diff
   stays reviewable). Record `baseline_commit` = `git rev-parse HEAD`.

## Stage 1 · Planning → the plan-accept gate

1. Invoke the **`np-plan`** skill with the requirement AND the intent:
   `"<requirement>. Dev intent (honor 100%): <intent verbatim>. defer_context_update=true"`. np-plan produces
   `01-plan-review.md` (C4 + method contracts + change/impact diagrams as ` ```plantuml ` blocks)
   and runs its own approve/revise loop — **that review IS this gate**. Relay the plan to the
   developer verbatim, and their feedback back into np-plan until they approve.
2. **On approval, publish the plan into the repo:** copy the approved `01-plan-review.md` (plus the
   phase table from `01-phases.json`) to **`plans/<run_id>.plan.md`** — create `plans/` at the repo
   root if missing. This file is committed with the work; the handoff dir stays the machine-state
   copy.
3. Record `run_id` + `plan_file`; park: `gate: awaiting_go_ahead`, `next_action: implementation`.
   Tell the developer exactly what to say to continue (`/np-loop advance`). **Wait.**

## Stage 2 · Implementation (on go-ahead only)

`/np-implement <run_id> defer_context_update=true` — phases run with their build/typecheck gates,
directly on the current branch. On return, present: phases completed, gate results,
the adversarial-review verdict from `review-report.md` (np-implement Step 4.5 runs the
`np-review` engine automatically), `git diff --stat <baseline_commit>`, pending findings count.
Park at `next_action: test`. **Wait.**

## Stage 3 · Test (on go-ahead only)

`/np-test <run_id> defer_context_update=true` — test generation, self-heal, ES capture (frontend: typecheck + visual QA).
Where the change has a runnable surface, also exercise it for real and report what you observed —
this stage often needs the developer's eyes; say so. Park at `next_action: review`. **Wait.**

## Stage 4 · Review (on go-ahead only)

The adversarial review (`np-review`) already ran inside Stage 2 — this stage adds the
project-conventions pass; do not re-run `np-review` unless the developer asks or Stage 2 skipped it.
Invoke the **`code-review-conventions`** skill over the task's changed files
(`git diff --name-only <baseline_commit>`), passing `handoff_dir=<run's handoff dir>` so it emits
`review-findings.json` there alongside `REVIEW-RESULT.md`. Present the findings by severity; if the
developer wants fixes, loop back to Stage 2 for a fix pass, then re-review. When findings recur or
the developer states a durable correction, route it through **`np-feedback`** so project context
learns it. Park at `stage: done` once the developer is satisfied. **Wait.**

## Done — the single context update

Only now, once the task is `stage: done`, spawn the **`context-updater`** agent with
`handoff_dir=<run's handoff dir>` and wait for `context-update-report.json`. It collects every
finding recorded across stages 1–4, dedupes by topic, and applies inserts/updates/supersedes in its
own context. One run, one report, at the end. Also run it when the developer abandons or permanently
parks a task that already produced findings — the alternative is losing them.

Then summarize: plan file, phases, gates, test results, review verdict, `git diff` pointer, and the
context updates from that report (inserted / updated / superseded ids, plus any `health` hint it
returned about a context file worth curating via `/np-context`). The developer reviews and
commits (they own git) — so end with the provenance block: the implement and test stages already
recorded this run's files into `<np-home>/np-provenance.jsonl` (do not record again here);
print `Provenance: … — commit it together with the change`, then
`git commit --trailer "Generated-By: np/<version> run=<run_id>"` and its git < 2.32 fallback
(`-m "<subject>" -m "<trailer>"`). After they open a PR, `/np-pr-review <pr>` reviews it in place; after big
landings suggest `/np-reindex`.

## At every gate

1. **In-session:** a compact stage summary + the exact next command.
2. **`PushNotification`** (one line, <200 chars, action first), e.g.
   `plan approved & saved to plans/ — say "advance" to implement`. Fine if not delivered.

## Hard rules

| Rule | Why |
|---|---|
| Never advance a stage without an explicit developer go-ahead | The human gate at every boundary is the whole point. |
| Never start planning before the intake interview + recorded `intent` | The plan must match the requirement AND the developer's intent. |
| You never write feature code — always dispatch the np loops | Conductor, not coder. |
| The approved plan MUST land in `plans/<run_id>.plan.md` before the implement gate opens | The plan is a committed, reviewable artifact, not buried machine state. |
| Work directly on the current branch — no worktrees, no copies | np's in-place contract; `git diff` vs `baseline_commit` is the review. |
| Never commit or push on the developer's behalf unless told | The developer owns git. |
| Project context is written once, by the `context-updater` sub-agent, at `stage: done` | Mid-run updates poison this conversation with bookkeeping and can persist knowledge a later stage contradicts (contract §8.1). |

## What this skill does NOT do

- Poll any ticket tracker, run any heartbeat, or start work by itself — the developer brings the
  requirement and drives every gate.
- Write feature code, tests, or plans itself (the np loops do).
- Create worktrees or branches — it stays where the developer is.
- Replace np-plan's review gate — it composes with it (Stage 1).
