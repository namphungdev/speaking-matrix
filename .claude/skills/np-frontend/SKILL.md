---
name: np-frontend
description: Frontend orchestration loop — resolve the frontend stack and template source, write the Mode B frontend-00-request.json handoff, drive the frontend-orchestrator (design → code → typecheck → visual verification), read back frontend-result.json, gate on the stack's typecheck command, and make sure context_findings reach the context-updater. Works standalone (/np-frontend "build X from <figma url>") and as the dispatcher np-implement invokes for frontend phases.
---

# np-frontend — Frontend Task Orchestration

You are a **thin orchestration wrapper** around the frontend agent pipeline. You do not write frontend source yourself — the `frontend-orchestrator` agent (and the agents it drives) does. Your job: preflight, resolve the template, write the Mode B handoff, invoke the agent, verify independently, and route findings.

Two invocation contexts, decided in Step 1:

- **Pipeline mode** — invoked by `np-implement` for a `"kind": "frontend"` phase of an approved plan.
- **Standalone mode** — invoked directly (`/np-frontend "build the checkout screen from <figma url>"`), no plan required.

## Step 0 — Preflight

1. Confirm `.claude/np.config.json` exists (walk up from cwd). If absent, stop: "np not initialized — run /np-init".
2. Read it: `harness.runs_root` (default `.np-runs`), `harness.handoff_dirname` (default `.codegen-handoff`), `stacks[]`, `frontend.template_source`.
3. Identify the **frontend stack**: the first stack whose `kind` matches `react*|vue|svelte|angular`, else the first stack declaring a `typecheck` command. Note its `kind` and `typecheck` command; if no frontend stack is configured, warn the dev (init may predate the frontend stack — suggest re-running `/np-init`) and use `npx tsc --noEmit` as the typecheck fallback.

## Step 0.5 — Model choice

- **Pipeline mode** (dispatched by `np-implement`): the caller already asked;
  use the model it passes you and forward it to the `frontend-orchestrator` and
  any other agent you spawn.
- **Standalone mode**: ask the dev yourself (`AskUserQuestion`, or a numbered prose
  question where that tool is unavailable) — **Sonnet
  (latest)** as the recommended default, **Opus (latest)** for visually
  intricate screens or when a previous attempt missed the design. Use the
  aliases `opus` / `sonnet`; default to `np.config.json` → `models.implement`,
  write the answer back there, and pass `model: "<choice>"` to every agent you
  spawn.

## Step 1 — Determine invocation context and the run dir

**Pipeline mode** — the args name an existing run (`run=<run_id> phase=<phase-id>`, a run id, or a run/handoff dir path whose `01-phases.json` contains a `"kind": "frontend"` phase):

- `handoff_dir = {runs_root}/{run_id}/{handoff_dirname}`; `run_dir` from the run's `00-request.json`. Reuse them — never mint a new run dir.
- Read the named phase (or the sole frontend phase) from `01-phases.json`: its `goal` is the request text; its `frontend` block supplies `feature_name`, `screens`, `design_source`, `template_source`, `conventions`.
- **Multi-frontend-phase guard:** if a `frontend-result.json` from an earlier frontend phase already exists in this handoff dir, **archive it** before this phase overwrites it — copy it to `frontend-result-<that phase's id>.json` (`cp` via Bash, or read + `np_write_handoff`). The updater collects `*-result.json`, so the archived findings are picked up at the end of the session along with everything else. Do NOT spawn the updater here: preserving the findings is the goal, and a mid-run updater pass is the expensive way to get it.

**Standalone mode** — the args are free text (usually with a Figma URL). Write a **minimal run dir** so results and findings are captured like any other run:

1. `run_id` = `<YYYYMMDD-HHMMSS>-<kebab-slug>` (slug ≤ 5 words from the request); `run_dir = {runs_root}/{run_id}`; `handoff_dir = {run_dir}/{handoff_dirname}`; `mkdir -p` both. The run dir holds handoffs/artifacts only — code changes happen in the repo's frontend app directly.
2. Write the minimal request:

```
np_write_handoff(handoff_dir, "00-request.json", {
  "agent": "np-frontend",
  "request": "<full args text>",
  "task_type": "frontend",
  "mode": "scaffold",
  "run_dir": "<run_dir>",
  "baseline_commit": "<git rev-parse HEAD, or null>",
  "preexisting_dirty": ["<git status --porcelain=v1 -uall --no-renames | cut -c4- — files already dirty before this run; never attributed to it>"],
  "review": false
})
```

3. Derive `feature_name` (kebab-case, from the request) and `screens` (one entry per Figma URL in the args, in order; `desktop_url` = the URL, `mobile_url` = null unless the request pairs one). No Figma URL and no other design source → ask the dev for one before proceeding.

## Step 2 — Resolve the target app (in the repo, in place)

1. `frontend_path` = the **absolute path of the real frontend app in the repository** that this task targets: the frontend stack's first `roots` entry (e.g. `<repo>/web`), or, in pipeline mode, the app the phase's `frontend` block names. If the repo has several frontend apps and the request doesn't disambiguate, ask the dev which one.
2. If `{frontend_path}/package.json` exists → the task **edits that app in place**, exactly like normal Claude Code edits. No template is involved. Check `git status --porcelain` for the app dir; if dirty, tell the dev and recommend commit/stash first (non-interactive: proceed and list the pre-existing dirty files in the summary).
3. Only when the repo has **no frontend app at all** does scaffolding apply — directly at the app's intended final location in the repo (confirm the location with the dev; never scaffold into the run dir). The orchestrator scaffolds **from scratch by default**; `frontend.template_source` (config, or the `FRONTEND_TEMPLATE_SOURCE` env var) is an OPTIONAL starter to copy from and is never required. **Never treat another project as a styling/pattern reference** — once an app exists, its own code and `project_context` are the only pattern sources; the Figma design supplies the visuals.

## Step 3 — Write the Mode B request handoff

```
np_write_handoff(handoff_dir, "frontend-00-request.json", {
  "agent": "np-frontend",
  "handoff_version": 2,
  "feature_name": "<feature_name>",
  "request": "<request text / phase goal>",
  "frontend_path": "<absolute path of the target app in the repo>",
  "artifacts_dir": "<absolute run_dir>/frontend-artifacts",
  "result_path": "<absolute handoff_dir>/frontend-result.json",
  "template_source": "<TEMPLATE or ''>",
  "figma_frame_steps": [
    {"step_label": "<screen label>", "desktop_url": "<figma url or null>", "mobile_url": "<figma url or null>"}
  ],
  "prefetched_artifacts": false,
  "conventions": ["FE1", "..."]          // pipeline mode: from the phase's frontend block; standalone: omit or []
})
```

Notes:

- `result_path` MUST point at `frontend-result.json` inside the handoff dir — that filename is how the context-updater and the calling loops find the result.
- `prefetched_artifacts: false` records that no server pre-computed Figma artifacts for this run (unlike the legacy server pipeline this handoff shape comes from) — the orchestrator must fetch design context itself.
- Use absolute paths for `frontend_path`, `artifacts_dir`, `result_path` — the agent locks onto them verbatim.

## Step 4 — Invoke the frontend-orchestrator

Spawn the `frontend-orchestrator` agent (Task tool subagent; fallback: read `.claude/agents/frontend/frontend-orchestrator.md` and inline it as the Task prompt) with these instructions:

> Mode B server handoff. Read `<handoff_dir>/frontend-00-request.json` first and use its `frontend_path`, `artifacts_dir`, and `result_path` verbatim. Because `prefetched_artifacts` is false, design artifacts are NOT pre-computed for this run — run your Step 0 (Fetch Figma Designs) against the `figma_frame_steps` URLs before scaffolding, saving reference JSON and screenshots into `artifacts_dir` under your standard names. Then follow your full pipeline **working on the app at `frontend_path` in place** — it is the repository's real frontend app, not a copy; scaffold from `template_source` only if no app exists at that path (assets, theme, layout, routes, steps, TypeScript verification, visual verification). Never copy the app elsewhere and never write source files into the run/handoff dir. Consult `.claude/project_context/conventions.md` and `architecture.md` per your protocol when they exist. Write your result JSON to `result_path` (`frontend-result.json`), appending `context_findings[]` per the contract when you learned something durable.

Wait for completion.

## Step 5 — Read back the result and gate on typecheck

1. `np_get_handoff(handoff_dir, "frontend-result.json")`. Missing → the run failed; report what the agent got through (list `frontend_path` and `artifacts_dir`) and stop with the failure path of Step 7.
2. **Independent typecheck gate** — do not take `typescript_check: "passed"` on faith: run the frontend stack's `typecheck` command yourself via Bash with `frontend_path` as cwd (fallback `npx tsc --noEmit`). Non-zero exit → the task is NOT done, whatever the result file claims; trust your own run. This is the same gate `np-implement` applies to frontend phases.
3. `status` is `"success"`, `"partial"`, or `"failed"`. `partial`/`failed` → collect `errors[]` and what remains for the failure summary.

## Step 6 — Route findings to the updater

Contract §8.1: findings are recorded here, applied once at the end of the session by the sub-agent.

- **Pipeline mode (or `defer_context_update=true`):** do NOT spawn the context-updater — the calling skill applies findings at the end of the session (its freshness check covers `frontend-result.json` and the Step 1 archives). Just confirm `frontend-result.json` is in place and report its `context_findings` count to the caller.
- **Standalone mode:** you are the last stage of this session. If `frontend-result.json` (or an archived `frontend-result-<phase-id>.json`) carries a non-empty `context_findings` array, spawn the `context-updater` agent with `handoff_dir=<handoff_dir>`, wait, read `context-update-report.json`, and relay the counts. Empty findings → skip the updater and say so.

## Step 6.5 — Record provenance (standalone mode only)

`np_record_provenance(handoff_dir, "frontend")` — the app was edited in place and the dev commits by hand; the committed ledger `<np-home>/np-provenance.jsonl` is what later proves which files np wrote (git blob hashes; idempotent; `preexisting_dirty` subtracted). Keep the returned `trailer` and `ledger_rel` for Step 7. In **pipeline mode do not record** — `np-implement` records once for the whole run at its end. Skip when `np.config.json` → `provenance.enabled` is `false`.

## Step 7 — Summarize

- run id + handoff dir, `frontend-result.json` status,
- files created/modified, route path, steps generated, visual verification (performed? steps checked),
- typecheck result — **yours from Step 5.2**, not the reported one,
- context findings emitted / context updates applied (standalone),
- where the code lives (`frontend_path` — the repo's app, changed in place) and next steps: pipeline mode → return control to `np-implement` (it writes the phase result); standalone → review `git diff`, then `/np-test <run_id>`, commit when satisfied.
- standalone only — **provenance**, the same block `np-implement` prints in its Step 6: `Provenance: <N> files recorded → <ledger_rel> — commit it together with the change`, then `git commit --trailer "<trailer>"` and its git < 2.32 fallback.

On failure: the first errors (typecheck output / `errors[]`), what the orchestrator's self-heal attempted, and pointers to the exact files (`frontend-00-request.json`, `frontend-result.json`, `artifacts_dir` screenshots).

## DO NOT

- Write or edit frontend source files yourself — the frontend agents do; you orchestrate.
- Copy styling or structure from any project other than the target app itself — the current app's code + `project_context` are the pattern source; Figma is the visual source. `template_source` exists only to seed a brand-new app.
- Report done while your own typecheck run fails, regardless of `typescript_check` in the result file.
- Spawn the context-updater in pipeline/deferred mode, or mid-run for any reason — the Step 1 guard *archives* the earlier phase's `frontend-result.json` instead. Never skip the updater in standalone mode when findings exist.
- Overwrite an earlier phase's `frontend-result.json` without archiving it first (Step 1) — that is the one way findings get silently lost.
- Mint a new run dir in pipeline mode — reuse the caller's handoff dir and run dir.
- Write source files anywhere except the repo's own app at `frontend_path` — the run dir is for handoffs and design artifacts only.
- Rename the handoff files: the request is `frontend-00-request.json`, the result is `frontend-result.json`, always in the run's handoff dir.
