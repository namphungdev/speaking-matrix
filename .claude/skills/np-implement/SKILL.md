---
name: np-implement
description: Implementation loop — take an approved plan from a np-plan run and execute it phase by phase, dispatching on phase kind (backend phases via the codegen agents with np_build_verify gates; frontend phases via the np-frontend skill with a typecheck gate), collect context_findings, and either defer them to the session's final stage or run the context-updater sub-agent when this IS the final stage. Use after /np-plan approval.
---

# np-implement — Execute an Approved Plan

You drive the execution half of the codegen pipeline. Input: a run created by `/np-plan` (or a `00-request.json` written with `review: false`). Output: build-verified code changes **in the repository working tree** (exactly like normal Claude Code edits — reviewed via `git diff`, committed by the dev), a `99-result.json`, and context updates. The run dir under `{runs_root}` holds pipeline state only — never code.

## Step 0 — Preflight and run resolution

1. Confirm `.claude/np.config.json` exists; read `harness.runs_root` (default `.np-runs`) and `harness.handoff_dirname` (default `.codegen-handoff`).
2. Resolve the run from the Skill args:
   - Args carry a run id → `handoff_dir = {runs_root}/{run_id}/{handoff_dirname}`.
   - Args carry a directory path → use it (it is either the handoff dir itself or the run dir containing it).
   - No args → pick the newest directory under `{runs_root}/` that contains `{handoff_dirname}/01-phases.json`; tell the dev which run you picked.
3. Verify the plan exists: `np_get_handoff(handoff_dir, "01-phases.json")`. If missing, stop: "no plan found — run /np-plan first".

## Step 1 — Approval gate

Read `00-request.json`:

- If `review` is `true`: `01-review-feedback.json` MUST exist with `"decision": "approved"`. If it is missing or `changes_requested`, stop: "plan not approved — finish the review loop in /np-plan". Never implement past an open review gate.
- If `review` is `false` (or absent): proceed.

## Step 1.2 — Model choice (ASK before executing)

Ask before any code is written (see the **Human gate** protocol below):

> **Which model should implement this plan?**
> - **Sonnet (latest) — recommended default.** The plan is already approved and
>   specifies the files, contracts and gates; execution is the cheaper, faster
>   half of the work.
> - **Opus (latest).** Pick it for intricate or high-risk changes — tricky
>   concurrency, a refactor across many call sites, or a plan the review flagged
>   as delicate.

Use the **aliases** `opus` / `sonnet` (always the current latest of that tier).
Default the question to `np.config.json` → `models.implement`, and mention what
model produced the plan (`00-request.json` → `model`) so the dev can match or
deliberately differ. After the answer:

- Pass `model: "<choice>"` to **every** Task-tool agent spawn in this run
  (orchestrator, planner, implementer, verifier, debaters/judge, frontend
  agents) — it overrides their frontmatter default. **If your host has no
  per-spawn model parameter** (sub-agents inherit the session model), say so in
  one line and tell the dev to switch it in the host's model selector before
  continuing — do not silently proceed as if the choice applied. Record it
  either way.
- Write the choice back to `np.config.json` → `models.implement`.
- You cannot change the main session's own model; say so plainly if the dev
  wants the session itself on that tier (`/model`, then re-invoke).

### Human gate — how to ask, and when not to

This protocol governs **every** dev-facing question in this skill.

**How:** use the `AskUserQuestion` tool when it is available. When it is not,
ask in prose instead — one question, options as a numbered list, the
recommended one marked `(recommended)` — then **END YOUR TURN and wait**.
**Never treat a missing tool as permission to skip the gate.**

**When not to:** skip the gate ONLY when the run is genuinely non-interactive,
i.e. ANY of:
- the session context contains `[np-noninteractive]`;
- `np.config.json` → `harness.interactive` is `false`;
- the invocation text already answers the question — honor it, never re-ask.

Then take the `np.config.json` default immediately, say in ONE line which
default you used and that the prompt was skipped, and carry straight on. A
phase that stops here has failed, not paused.


## Step 1.5 — Working-tree guard

Code is written directly into the repository working tree, so check `git status --porcelain` first. If the tree is dirty, tell the dev which files are already modified and recommend committing or stashing so the run's own diff stays reviewable; ask whether to proceed (in a non-interactive context: proceed, but list the pre-existing dirty files in the final summary so they are never attributed to this run).

Record what you found into `00-request.json` (read it with `np_get_handoff`, merge, write back with `np_write_handoff` — both fields are additive):
- `preexisting_dirty`: the dirty list **as files, not directories** — `git status --porcelain=v1 -uall --no-renames | cut -c4-` — so the review scope (Step 4.5) and the provenance record (Step 5.5) can subtract them exactly;
- `baseline_commit`: `git rev-parse HEAD`, only if the request carries none.

## Step 2 — Load context

Invoke the `load-context` skill with the request summary from `00-request.json` **and the `handoff_dir`** — the plan stage seeded `00-context.json` there, so this is a cache hit on the project frame (no re-read of `architecture.md`/`modules.json`) while the lesson search still runs fresh against *this* stage's needs. Note any active lessons/error-solutions relevant to the target module — if the orchestrator later hits errors these are the first things its verifier will search for.

## Step 3 — Drive the execution pipeline (dispatch on phase kind)

Read `01-phases.json` and split the phases by kind: a phase with `"kind": "frontend"` is a **frontend phase**; every phase without that key is **backend**. Backend phases run first (3a), frontend phases after (3b) — the plan orders them that way (fullstack plans append the frontend phase last).

### 3a — Backend phases (skip entirely when the plan has none, e.g. a frontend-only run)

Spawn the `codegen-orchestrator` agent (Task tool subagent; fallback: read `.claude/agents/codegen/codegen-orchestrator.md` and inline it as the Task prompt) with these instructions:

> Execution scope. Handoff dir: `<handoff_dir>`. **Spawn every sub-agent you invoke with `model: "<the Step 1.2 choice>"`** so the whole phase runs on the tier the dev picked. Working tree: the repository root — write all code changes in place, exactly where they will live; the run dir (`run_dir` in `00-request.json`) is for handoffs/artifacts only and must never contain code. Read `00-request.json` and the approved `01-phases.json` via `np_get_handoff` — do NOT re-decompose phases; the plan is dev-approved (also read `01-review-feedback.json` and honor its comments). Execute ONLY the phases whose `kind` is absent or not `"frontend"` — frontend phases are dispatched by the calling skill after you finish; do not write phase requests for them, do not execute them, and do not treat their pending state as a failure. For each phase, follow your protocol: write `phase-N-request.json` (carrying `module_context`), invoke `codegen-planner` → resolve your 4b.1 **decision gate** (`needs_debate` defaults to false; when true, use the dev's pick from `01-review-feedback.json` `decisions[]`, else the planner's `recommended` alternative — **do NOT spawn debate agents** unless `00-request.json` carries `"debate": true`) → `codegen-implementer` → gate the phase with `np_build_verify` on `module_context.build_target`. After all phases, invoke `codegen-verifier` (build + DI + mandatory test generation/execution) writing `99-verified.json`, then write `99-result.json`. Producers append `context_findings[]` to their result handoffs per the contract. Do NOT invoke the `context-updater` and do NOT write context entries yourself — findings stay in the handoff dir; the calling skill applies them once at the end of the session (contract §8.1).

(That instruction is unconditional — backend-only, frontend-included, standalone or loop-driven. No sub-agent below you ever runs the updater; Step 5 decides whether *this session* is the one that applies the findings.)

While it runs / after it returns, confirm progress by listing the handoff dir (`np_list_files(dir=handoff_dir, glob="phase-*-result.json")`).

**If the orchestrator stops on a failed phase gate:** read the failing `phase-N-result.json` and the `np_build_verify` errors it recorded. You may re-spawn the orchestrator ONCE with the instruction to resume from the failed phase — name it explicitly and list the already-completed phases: "Resume execution at phase `<N>`. Phases `<list>` completed successfully — per your Step 4 execution-stage resume rule, skip any phase whose `phase-N-result.json` has `status: success` and do not overwrite those results." (Its verifier self-heal already retried 3×; a second full retry beyond that needs a dev decision.) If it fails again, go to Step 6 (failure path) — but only **after finishing Step 5's updater bookkeeping**, mirroring the frontend failure path (Step 4's independent build re-run may be skipped for the known-failed build). Step 5 is the only thing that can process the `context_findings` already recorded by the phases that DID complete — and if Step 5 defers, the stage that follows picks them up. Do not start frontend phases while a backend phase gate is failing.

### 3b — Frontend phases (after all backend phases pass; skip when the plan has none)

For each frontend phase (resume rule applies here too — skip a frontend phase whose `phase-N-result.json` already has `status: success`):

1. **Dispatch to the `np-frontend` skill** (Skill tool name `np-frontend`; fallback: read `.claude/skills/np-frontend/SKILL.md` and follow it) with args naming this run and phase: `run=<run_id> phase=<phase-id>`. In pipeline mode that skill writes the Mode B `frontend-00-request.json` into this handoff dir (frontend_path / template_source / figma info taken from the phase's `frontend` block), invokes the `frontend-orchestrator` agent, and reads back `frontend-result.json`.
2. **Gate the phase on typecheck** — the mirror of the backend build gate. Resolve the frontend stack from `np.config.json` `stacks[]` (kind matching `react*|vue|svelte|angular`, else the stack declaring `typecheck`) and run its `typecheck` command yourself via Bash with the phase's frontend app dir (`frontend_path` from `frontend-00-request.json`) as cwd; fall back to `npx tsc --noEmit` if no `typecheck` command is configured. The phase is **NOT done** — regardless of what any result file claims — when the typecheck exits non-zero, when `frontend-result.json` is missing or has `"status": "failed"`, or when its `typescript_check` is not `"passed"`.
3. **Write the phase result** `phase-<N>-result.json` via `np_write_handoff`: `{"agent": "np-implement", "phase_id": "<phase-id>", "kind": "frontend", "status": "success" | "failed", "detail": "see frontend-result.json", "files_created": [...], "files_modified": [...], "typecheck": "passed" | "failed"}` (files copied from `frontend-result.json`). Carry **NO** `context_findings` in this file — the findings live in `frontend-result.json`; double-carrying would inflate the updater's evidence.
4. On a failed frontend phase: report the typecheck errors / `frontend-result.json` errors and go to Step 6 (failure path) after finishing Steps 4–5 bookkeeping.

**Findings folding:** `frontend-result.json`'s `context_findings` enter the pipeline set exactly like backend result handoffs — the `context-updater` collects `*-result.json` files and its source map routes `frontend-result.json → implementation`. Nothing extra to do here beyond ensuring the updater runs on a fresh state (Step 5).

## Step 4 — Independent verification gate

Do not take `99-result.json` on faith:

1. Read `99-result.json` and `99-verified.json` via `np_get_handoff`. **Frontend-only runs have neither** (no codegen-orchestrator ran) — the run's completion record is the `phase-N-result.json` files plus `frontend-result.json`; skip to point 4.
2. Re-run the build yourself: `np_build_verify(target=<module_context.build_target from a phase request, or 99-result data>)`. If `stacks[]` has more than one stack and the change touched several, verify each touched **backend** stack (`np_build_verify(stack_kind=..., target=...)`) — frontend stacks are verified in point 4, not here.
3. If your build result disagrees with the reported `build_passed`, trust your build, mark the run failed, and say so explicitly in the summary.
3.5. **Granularity**: read each `phase-N-result.json`'s `file_budget` and `escape_gate`. Report both in the summary — planned vs created file count per phase, and any path the escape gate could not fold. A phase whose `escape_gate` is `"failed"` or whose status is `failed` with `"reason": "granularity-gate"` is a failed run, exactly like a failed build; do not paper over it with "the code compiles".
4. **Frontend phases**: the Step 3b.2 typecheck run was already yours — that is the independent check. If Step 3b was executed in a delegated context (e.g. the np-frontend skill ran the typecheck), re-run the `typecheck` command yourself now; additionally, when the frontend stack declares a `build` command, run that build command via Bash with the phase's `frontend_path` (the real app root in the repo) as cwd — exactly like the typecheck. A failing typecheck or frontend build marks the run failed regardless of reported statuses.

## Step 4.5 — Adversarial review (after a PASSED Step 4)

If `np.config.json` → `review.enabled` is not false, invoke the `np-review` skill (Skill tool name `np-review`; fallback: read `.claude/skills/np-review/SKILL.md` and follow it) in pipeline mode: `handoff_dir=<handoff_dir>`, scope = this run's changed files (`git diff --name-only <baseline_commit>`, minus the pre-existing dirty files noted in Step 1.5, minus `**/np-provenance.jsonl` — the ledger is a machine record, never review scope), `min_impact` = `review.min_impact` (default `"medium"`). It conditionally spawns the reviewer agents in parallel, writes `review-findings-ext.json` into the handoff dir and `review-report.md` into the run dir, and returns a Quality Gate verdict.

- The verdict is information, not a gate: FAIL never flips a passed build to failed and never reverts anything — surface the critical/high issues in Step 6 and let the dev decide (fix by hand, re-run phases, or accept).
- Skip with one line when Step 4 failed (never review code that doesn't build), when `review.enabled` is false, or when the run changed no files.
- Do NOT spawn the `context-updater` here — `review-findings-ext.json` is collected by Step 5 like every other findings file.

## Step 5 — Context updater: defer or run, per contract §8.1

The updater runs **once, in the final stage of the session**, as a sub-agent — never inline, never mid-pipeline.

1. **Am I deferring?** Yes when the args carry `defer_context_update=true`, when `np-loop` invoked you (the loop drives `/np-test` and review after this), or when the dev has already said they will run `/np-test` next. Then: do NOT spawn the updater. Count the findings sitting in the handoff dir, note `"context_update": "deferred"` in `99-result.json`, report the pending count in Step 6, and stop here.
2. **Otherwise this run is the final stage.** Check for `context-update-report.json` in the handoff dir — and check **freshness, not mere presence**: a plan-stage run may have left a report that predates the implement stage entirely. The report is **stale** when either:
   - its `processed_files` array (written by the updater) does not list the implement-stage findings files (`phase-*-result.json`, `99-verified.json`, `review-findings-ext.json` when Step 4.5 ran, and — when a frontend phase ran — `frontend-result.json`), or
   - lacking that field, any findings-carrying handoff file is **newer** than the report (compare mtimes with `ls -lt` / `stat`).
3. If the report is missing **or stale** and any findings-carrying handoff (`*-result.json` — including `frontend-result.json` and its `frontend-result-<phase-id>.json` archives — `phase-*-todos.json`, `99-verified.json`, `review-findings.json`, `review-findings-ext.json`, or `01-review-feedback.json`) carries `context_findings`, spawn the `context-updater` agent with `handoff_dir=<handoff_dir>` and wait for the refreshed report.
4. Read the report and fold its counts into your summary.

Note the asymmetry, and keep it: deferring is cheap (the next stage runs the updater against the same dir, and its `processed_files` dedupe means nothing is lost or double-counted), while running it mid-pipeline burns context and can persist findings that a later phase contradicts.

## Step 5.5 — Record provenance (always, right before the summary)

The dev commits by hand, so nothing in git says which files this run wrote. Record it now, while the files are final for this stage:

```
np_record_provenance(handoff_dir, "implement")
```

It takes the touched set from git (changes since `baseline_commit` plus untracked files, minus `preexisting_dirty`), hashes each file with its git blob id, and appends to the committed ledger `<np-home>/np-provenance.jsonl`. It is idempotent — re-running after a fix only re-records files whose content changed. Fallback when the MCP server is down: `python3 ".claude/scripts/provenance.py" record <handoff_dir> --stage implement`.

Keep the result's `trailer` and `ledger_rel` for Step 6. `success: false` with a gitignore error means the repo ignores the ledger's directory — say so plainly; provenance cannot be committed until `.gitignore` is fixed. Skip this step only when `np.config.json` → `provenance.enabled` is `false`, and say so in one line.

## Step 6 — Summarize

**Success** (backend phases: build passed, DI passed, ≥1 test executed, 0 failed — per `99-result.json` and your Step 4 check; frontend phases: typecheck passed, `frontend-result.json` status `success`, visual verification performed):

- run id, phases completed, files created/modified (from `99-result.json`; for frontend phases from `frontend-result.json`),
- **files created vs planned**, one line: `<created> new files (plan: <N>, anchor `<module>`: <M>)` from the phases' `file_budget`, plus anything the escape gate folded back or could not fold,
- build + DI status, test pass percentage; for frontend phases: typecheck status, steps visually verified, route path,
- the Step 4.5 adversarial-review verdict (quality gate + critical/high counts) with a pointer to `review-report.md` in the run dir — or the one-line reason it was skipped,
- **any `decision` recorded in a `phase-N-result.json`** — name the phase, the chosen approach, and its `source`. Call out `source: "planner-recommendation"` explicitly: that fork went unchosen by the dev, and this summary is their last chance to catch it before the diff.
- context: deferred → "N findings recorded, applied at the end of the run"; otherwise the inserted/updated/superseded counts from `context-update-report.json`,
- the changed files are in the working tree — point the dev at `git diff` (against `baseline_commit` when recorded) and any pre-existing dirty files noted in Step 1.5; next step: `/np-test <run_id>` for the deeper test loop, then review the diff and commit.
- **provenance** (from Step 5.5) — exactly this block, so the reviewer of the eventual PR can prove which files np wrote:

  ```
  Provenance: <N> files recorded → <ledger_rel> — commit it together with the change.
    Stage your changes and the ledger, then:
    git commit --trailer "<trailer>"
    (git < 2.32: git commit -m "<subject>" -m "<trailer>")
  ```

**Failure**:

- which phase/gate failed and the first errors (from the relevant `phase-N-result.json` / `99-verified.json`),
- what the self-heal loop attempted,
- pointers: exact handoff files to inspect, and suggested next actions (fix by hand in the working tree and re-run `/np-test`, revert with `git checkout`/`git restore` if the run should be discarded, or re-plan via `/np-plan` if the plan itself was wrong).
- Still report any context updates that DID land — a failed run can still teach (error-solutions are captured by the verifier/test loop).

## DO NOT

- Implement past an open review gate (`review: true` without an `approved` feedback file).
- Re-decompose or silently alter the approved `01-phases.json` — plan changes go back through `/np-plan`.
- Write or edit source files yourself — all code changes go through the codegen agents (backend) or the frontend agents via `np-frontend` (frontend).
- Dispatch a frontend phase to the codegen agents, or a backend phase to `np-frontend` — the phase `kind` decides, nothing else.
- Mark a frontend phase done while its typecheck fails — failing tsc = phase not done, exactly like a failing backend build.
- Copy `frontend-result.json`'s `context_findings` into `phase-N-result.json` — findings are collected from `frontend-result.json` directly.
- Skip the independent verification in Step 4 (backend `np_build_verify` / frontend typecheck + build run via Bash from `frontend_path`), or report success when it fails.
- Write context entries yourself (`context_add_entry`, `context_supersede`, edits under `project_context/`) — the `context-updater` sub-agent is the only writer (contract §8.1).
- Let the **session** end without `context-update-report.json` when findings exist. (Ending *this skill* without one is correct when Step 5 deferred — say so in the summary, and name the stage that will apply them.)
