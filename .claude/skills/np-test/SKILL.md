---
name: np-test
description: Test loop — drive test generation via the codegen-verifier (backend, np_test_run) or the frontend-verifier's typecheck + visual-QA loop (frontend, stack commands via Bash from the frontend app root), self-heal failures by consulting error-solution lessons (ES entries), record errors healed without a prior lesson as error-solution findings for the context-updater sub-agent, and summarize. Use after /np-implement or standalone against a module.
---

# np-test — Test Loop with Lesson-Backed Self-Healing

You generate/run tests, heal failures using the project's accumulated error-solutions, and pay the knowledge forward: every error you heal that had no lesson becomes an error-solution finding, which the `context-updater` sub-agent turns into an ES entry at the end of the session. You read lessons; you never write them (contract §8.1).

## Step 0 — Preflight and target resolution

1. Confirm `.claude/np.config.json` exists; read `stacks[]`, `harness.runs_root` (default `.np-runs`), `harness.handoff_dirname`. If absent, stop: "np not initialized — run /np-init".
2. Resolve the target from the Skill args:
   - **Run id / run dir** → `handoff_dir = {runs_root}/{run_id}/{handoff_dirname}`; the code under test lives **in the repository working tree** (the run's changes were made in place; the run dir holds only handoffs/artifacts); take `stack_kind` and `target` from the run's `module_context` (`build_target`, adjusted to the stack's test target convention).
   - **Module name or path** → work against the repo directly; find its stack by matching `stacks[].roots`; discover the test target (never template it): list the module for test projects/configs (e.g. `*.Tests.csproj`, `vitest`/`jest` config) with `np_list_files` or Glob.
   - **No args** → pick the newest run under `{runs_root}/` with a `99-result.json` (or, for frontend-only runs which have none, a `frontend-result.json`); tell the dev which run you picked. If none, ask what to test.
3. If run-based, create nothing new — reuse the run's handoff dir for all files you write.
4. **Frontend target?** The target is frontend when: run-based and the run's `00-request.json` has `task_type: "frontend"`, or its `01-phases.json` contains a `"kind": "frontend"` phase (a `fullstack` run tests its frontend part with the frontend branches below and its backend part with the normal ones); or module-mode and the module path falls under a **frontend stack**'s `roots` — a stack whose `kind` matches `react*|vue|svelte|angular`, or any stack declaring a `typecheck` command. When frontend, note the stack's `kind`, its `typecheck` command (fallback `npx tsc --noEmit`), and the frontend app root (`frontend_path` from the run's `frontend-00-request.json` when run-based, else the module path).

## Step 1 — Load context

Invoke the `load-context` skill with the target summary — **and, in run-based mode, the `handoff_dir`**, so the project frame comes from the run's cached `00-context.json` rather than another read of `architecture.md`. In module mode there is no run and no cache; it reads the sources. Either way its lesson search runs fresh. Additionally pre-load the error-solution memory for this stack:

> **Resolving the code-search tool (do this before your first search).** The
> `search` tool is served by the **`np-code-search` MCP server**. Every host
> renames MCP tools with its own prefix, so do NOT assume a literal name — in
> Claude Code it appears as `mcp__plugin_np_np-code-search__search`; other
> hosts use a different prefix. Its schema may also be **deferred**, i.e. not
> loaded into your context yet, and the server may still be connecting at the
> start of a session. Resolve it in this order:
>   1. look for any available tool whose name ends in `search` and whose server
>      is `np-code-search`, and call it;
>   2. if your host has a deferred-tool loader (Claude Code: `ToolSearch`), call
>      it with the keywords `np-code-search search` — it also waits out a
>      server that is still connecting — then call the tool;
>   3. last resort, run the CLI twin, which ships with every install:
>      `bash .claude/bin/ccc-wrapper.sh grep "<query>"`.
>
> **Never silently fall back to Read/Grep because the tool "isn't there":**
> file reads miss the whole index. If it is genuinely unavailable after all
> three, say so explicitly in your output and note that results are degraded —
> do not pretend the index was consulted.

```
search(query="<stack kind> build test errors <target module>", limit=5,
       paths=[".claude/project_context/lessons/**"])
```

(`search` is the `np-code-search` MCP tool.) Keep the surfaced ES entries at hand — they are your first line of healing.

## Step 2 — Baseline test run

**Frontend target — run both gates via Bash with the frontend app root (from Step 0.4: the `frontend_path` recorded in `frontend-00-request.json` when run-based — the repo's real app — else the module path) as cwd:**

1. **Typecheck first:** the frontend stack's `typecheck` command (fallback `npx tsc --noEmit`). A failing typecheck is a failure to heal in Step 4 exactly like a failing test — tsc error lines slot into the same lessons-search → fix → re-run loop.
2. **Then the frontend stack's `test` command** (e.g. `npx vitest run`), same cwd; parse the summary and failing test names from its output. Do NOT use `np_test_run` for a frontend target: frontend test commands carry no `{target}` placeholder — running them via Bash from the frontend app root guarantees the right cwd in both modes.

**Backend target:**

```
np_test_run(stack_kind=<kind>, target=<test target>)
```

- Tests exist and all pass (and, for frontend, typecheck passes) → skip to Step 5 (still consider coverage: if the run's changed files have no covering tests, continue to Step 3).
- Failures → note `summary` + `failures[]`, go to Step 4.
- **Zero tests executed** (or no test target found) → tests must be generated first: Step 3.

## Step 3 — Test generation (via the verifier)

**Frontend target:** the typecheck + visual-QA self-heal loop is the frontend equivalent of test generation and healing.

- **Run-based** (the handoff dir contains `frontend-00-request.json`): spawn the `frontend-verifier` agent (Task tool subagent; fallback: read `.claude/agents/frontend/frontend-verifier.md` and inline it as the Task prompt) pointing it at `<handoff_dir>/frontend-00-request.json` — it re-runs tsc, self-heals TypeScript errors, and performs visual verification against the run's Figma screenshots. (That request's `result_path` is the run's `frontend-result.json`; the verifier's Step 6 clobber guard keeps the orchestrator's existing result keys intact and adds its record under a `verification` key.) Per its protocol, a fix that required a non-obvious workaround becomes an `error-solution` finding appended to `frontend-result.json` (frontend agents do NOT write ES entries directly — the updater does; Step 6 routes them). Then continue to Step 4 with whatever tsc/test failures remain (heal those yourself).
- **Module-mode** (no run artifacts, so no design screenshots to compare against): skip the visual loop; treat failing typecheck/tests through the normal Step 4 self-heal loop, and if the stack has no test setup at all, tell the dev — do not scaffold a frontend test framework unasked.

**Backend target:** spawn the `codegen-verifier` agent (Task tool subagent; fallback: read `.claude/agents/codegen/codegen-verifier.md` and inline it as the Task prompt) scoped to test generation:

> Test-generation scope. Workspace: the repository working tree (target module: `<module path>`). Handoff dir: `<handoff_dir>` (if run-based). Generate test cases for `<the changed files from 99-result.json, or the target module>` per your protocol (tests are mandatory; zero executed tests is a failure), execute them via `np_test_run(stack_kind=..., target=...)`, self-heal per your protocol, and record results into **`99-test-verified.json`** when part of a run — NEVER overwrite the implement stage's `99-verified.json`; it is the prior verification record (fixes_applied, error_solutions_recorded, original test counts) and must stay intact.

Then re-run `np_test_run` yourself to get an independent baseline of the generated suite. Continue to Step 4 with any remaining failures.

## Step 4 — Self-heal loop (max 3 iterations)

For each iteration while failures remain:

1. **Consult the lessons first.** For each distinct failure (error code/message or failing test + assertion):

   ```
   search(query="<error code / first error line / failing assertion>", limit=5,
          paths=[".claude/project_context/lessons/**"])
   ```

   If an active ES entry matches, apply its documented fix (adapted to the file at hand). Record: `error → fix → source: <ES id>`.
2. **No lesson?** Diagnose: root cause, minimal fix, no new functionality, conventions respected (run the `conventions` skill's Pre-Write Checklist before saving any source edit). Apply the fix. Record: `error → fix → source: new`.
3. Re-run the Step 2 baseline (backend: `np_test_run`; frontend: the stack's `test` command via Bash from the frontend app root, plus the `typecheck` command — a heal only counts when both are green). Progress check: if the failure set is unchanged two iterations in a row, stop early — flailing edits make the working tree worse.

After the loop (or if 3 iterations exhausted), classify each originally-failing error as **healed** (now passes) or **unresolved**.

## Step 5 — Record new error-solutions as findings (do not write entries here)

For every **healed** error whose fix did NOT come from an existing ES entry, record a finding. You do **not** call `context_add_entry`, match against existing entries, or `context_sync` — that bookkeeping belongs to the `context-updater` sub-agent (contract §8.1), which also does the dedupe far better than a one-shot search: it matches by topic and then fuzzily across the whole lessons dir.

Build one finding per healed error, to fold into `test-result.json` in Step 6:

```json
{"topic": "error-<error-code-kebab>", "kind": "error-solution",
 "claim": "<error code/signature>: <one-line summary of the fix>",
 "evidence": ["Error: <exact error output>",
              "Root cause: <one sentence>",
              "Fix: <the minimal change, with file path and the edit described concretely>",
              "Verification: <test command that now passes>"],
 "supersedes": null, "confidence": "observed", "modules": ["<TargetModule>"]}
```

For healed errors whose fix DID come from an existing ES entry, produce no finding — the entry proved itself; mention it in the summary instead.

## Step 6 — Write the result handoff and capture non-ES knowledge

**Run-based:**

```
np_write_handoff(handoff_dir, "test-result.json", {
  "agent": "np-test",
  "summary": {"passed": N, "failed": N, "skipped": N},
  "healed": [{"error": "<signature>", "fix_source": "<ES id | new>"}],
  "unresolved": ["<failure names/lines>"],
  "context_findings": [ ...Step 5's error-solution findings, PLUS any non-ES observation
                        worth keeping (e.g. a durable lesson about the test setup)... ]
})
```

Then apply the §8.1 rule:

- **Deferred** — args carry `defer_context_update=true`, `np-loop` invoked you, or a review stage is still to come on this handoff dir. Record `"context_update": "deferred"` in `test-result.json`, report the pending finding count, spawn nothing.
- **Final (the usual case for a standalone `/np-test`)** — you are the last stage touching this handoff dir. Spawn the `context-updater` agent with `handoff_dir=<handoff_dir>` when **any** findings-carrying handoff is not yet covered by a fresh `context-update-report.json`: your own `test-result.json`, `99-test-verified.json` (Step 3's verifier records test-layout quirks there), or `frontend-result.json` and its `frontend-result-<phase-id>.json` archives. Check coverage via the report's `processed_files`/mtime, exactly like the implement skill. Your own findings array being empty is NOT a reason to skip — someone else's may not be.

**Module-mode (no run):** there is still no inline entry writing. Mint a minimal run dir so the findings have somewhere to live and the sub-agent has something to read:

1. `run_id` = `<YYYYMMDD-HHMMSS>-test-<module-kebab>`; `handoff_dir = {runs_root}/{run_id}/{handoff_dirname}` (both from `np.config.json`).
2. `np_write_handoff(handoff_dir, "test-result.json", {...})` with the same shape as above.
3. Spawn the `context-updater` with that `handoff_dir` — module-mode is always final mode.

## Step 6.5 — Record provenance

Generated and healed test files are edits in the working tree that the dev commits by hand. `np_record_provenance(handoff_dir, "test")` appends them (git blob hashes) to the committed ledger `<np-home>/np-provenance.jsonl` so a PR reviewer can later prove np wrote them. Idempotent — files the implement stage already recorded and did not change come back as `unchanged`. Keep the returned `trailer` and `ledger_rel` for Step 7. Skip when `np.config.json` → `provenance.enabled` is `false`.

## Step 7 — Summarize

- Final test counts (passed/failed/skipped) and pass percentage.
- Healed errors: which were healed **from** an existing ES entry (cite ids — the feedback loop working), and which produced **new** error-solution findings (cite the new ES ids from `context-update-report.json` when the updater ran here; otherwise say "N recorded, applied at the end of the run").
- Unresolved failures with the exact error lines and the file(s) involved — these need the dev.
- If run-based: point at `test-result.json` and (when written) `context-update-report.json`.
- **Provenance** — the same block `np-implement` prints in its Step 6: `Provenance: <N> files recorded → <ledger_rel> — commit it together with the change`, then `git commit --trailer "<trailer>"` and its git < 2.32 fallback.

## DO NOT

- Skip the lessons search before diagnosing a failure from scratch.
- Add functionality, weaken assertions, or delete/disable failing tests to force green.
- Call `context_add_entry` / `context_supersede` / `context_sync`, or edit anything under `project_context/`, yourself — every entry write is the `context-updater` sub-agent's job (contract §8.1). Your Step 4 lessons *search* stays; it is a read.
- Let the **session** end without a fresh `context-update-report.json` when any handoff carries `context_findings` — gate the updater on ANY findings-carrying handoff (Step 6), not only your own `test-result.json`. (Ending *this skill* without one is correct in deferred mode.)
- Exceed 3 self-heal iterations or keep editing when two iterations show identical failures.
- Report success when zero tests executed, or — for a frontend target — while the typecheck command fails.
