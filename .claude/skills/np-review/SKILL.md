---
name: np-review
description: Adversarial multi-agent code review — resolve the scope (a run's baseline diff, uncommitted changes, or explicit files), conditionally spawn up to 6 parallel reviewer agents (bug hunter, security, code quality, contracts, test coverage, historical context), score findings by impact/confidence with a min-impact threshold, and emit a terminal report plus review-findings-ext.json (pipeline mode) whose context_findings feed the context-updater. Complements code-review-conventions — this engine hunts generic bugs/security/contract issues; that one enforces the project's conventions.md.
---

<!-- Orchestration adapted from NeoLabHQ/context-engineering-kit, plugins/review
     v3.2.0 (GPL-3.0), skills/review-local-changes/SKILL.md.
     See THIRD-PARTY-NOTICES.md at the ver2 root. -->

# np-review — adversarial review engine

Two modes, decided by the args:

- **Pipeline** (invoked by `np-implement` Step 4.5, `np-patch` Step 6, `np-pr-review` Step 3.5): args carry `handoff_dir=<dir>` plus a scope (file list and/or diff base), `min_impact=<level>`, and optionally `agents=[...]` (a forced subset).
- **Standalone** (`/np-review "[aspects] [--min-impact critical|high|medium|medium-low|low] [run-id|files…]"`): free-text aspects focus the review; a run id resolves to that run's baseline diff; with nothing given, the scope is the uncommitted changes (staged + unstaged + untracked, skipping `.np-runs/` and `.claude/`).

## Step 0 — Preflight and config

1. Walk up to the nearest `.claude/np.config.json`; absent → stop: **"np not initialized — run /np-init"**.
2. Read `review.{enabled, min_impact, patch_min_impact, agents}` (defaults: `true`, `"medium"`, `"medium"`, all six agents) and `models.review` (default `sonnet`). An explicit `min_impact`/`agents` in the args overrides config.
3. `review.enabled: false` in pipeline mode → say so in one line, write nothing, return. Standalone → the dev asked explicitly; proceed.
4. Resolve `MIN_IMPACT_SCORE` from the level: `critical` → 81, `high` → 61, `medium` → 41, `medium-low` → 21, `low` → 0.

## Step 1 — Resolve scope

Priority: explicit file list > run scope (`git diff <baseline_commit> --name-only`, minus the run's `preexisting_dirty` list from `00-request.json`) > uncommitted changes (`git status --short`, `git diff --stat`, `git diff --cached --stat`).

Always drop `**/np-provenance.jsonl` from the scope — the ledger is a machine record that every later stage of a run modifies, never something to review.

Record: the file list, per-file changed-line counts, and the **exact diff command(s)** reviewers will run (e.g. `git diff <baseline_commit> -- <files>`, or `git diff` + `git diff --cached` for uncommitted). Empty scope → say so and stop.

Also call `np_verify_provenance(files=<scope>)` once (cheap: hashes the scoped files against the committed ledger) and keep its `summary` for the report header — which of these files np wrote, and whether they have been edited since.

## Step 2 — Summarize the change (cheap)

- Total diff ≤ ~400 lines: read the diff yourself and write a 5–10 line change summary (per file: what changed, complexity, affected symbols).
- Larger: spawn 1–2 **haiku** Task agents over file groups, each returning a per-file summary; concatenate.
- Collect guideline file **paths only** (never contents): root `CLAUDE.md`, root `README.md`, and `README.md` in the directories of touched files.

## Step 3 — Select agents (conditional spawn — this is the cost control)

Start from `review.agents` (or the caller's forced subset — `np-patch` forces `[review-bug-hunter, review-security-auditor]`) and prune by what the diff actually contains:

| Agent | Spawn when |
|---|---|
| `review-bug-hunter` | any code or config change (skip only doc-only diffs). **The floor: if only it qualifies, it runs alone.** |
| `review-security-auditor` | any non-test source or config change; skip pure renames/formatting/doc-only/test-only diffs |
| `review-code-quality` | any code change beyond pure formatting |
| `review-test-coverage` | ≥1 non-test source file changed, or test files changed; skip doc/config-only |
| `review-contracts` | the diff touches public surface: exported/public signatures, DTO/entity/model/schema/migration/`.proto`/OpenAPI files, or dependency manifests |
| `review-historical-context` | ≥5 files or >200 diff lines, OR a touched file's `git log --oneline -10 -- <file>` shows fix/revert churn, OR `.claude/project_context/lessons/**` names a touched module |

Total diff < ~10 changed lines → `review-bug-hunter` only (unless the caller forced a subset). Never more than 6 agents; never background agents — foreground parallel Tasks only.

## Step 4 — Spawn reviewers in parallel

One Task per selected agent, `model: <models.review>`, ALL spawns in a single message. Spawn by agent name (`review-bug-hunter`, …); if named agents are unavailable, read `.claude/agents/review/<name>.md` and inline it as the Task prompt. Each spawn prompt carries:

1. The **scope block**: file list, the exact diff command(s) from Step 1, the change summary from Step 2, guideline file paths, and any free-text review aspects from the args.
2. The **scoring rubric** (each agent self-scores; you normalize in Step 5):

> **Confidence (0–100)** — that the issue is real, not a false positive: 0 = doesn't survive light scrutiny or is pre-existing; 25 = might be real, unverified; 50 = verified real but possibly a nitpick or rare in practice; 75 = double-checked, very likely hit in practice, directly impacts functionality; 100 = certain, frequent, evidence confirms it.
> **Impact (0–100)** — consequence if unfixed: 0–20 minor smell; 21–40 hurts maintainability, no functional impact; 41–60 errors under edge cases / performance degradation; 61–80 breaks core features or corrupts data under normal use; 81–100 runtime errors, data loss, crash, security breach, or complete feature failure.

3. The reminder: **return text findings only; never write files; conventions.md rules are out of scope.**

A reviewer Task that errors or returns nothing degrades to a warning in the report ("review incomplete — <agent> failed") — never fail the review, never re-spawn more than once.

## Step 5 — Score, filter, merge

1. Normalize the agents' self-scores against the rubric yourself (an agent that scored everything 90+ gets pulled back to evidence). Spawn a batch of **haiku** scorer Tasks (one per issue, all in one message) ONLY when more than 10 issues survive the merge — otherwise your own judgment is the scorer.
2. Merge duplicates across agents — same file + overlapping lines + same substance → one issue, keep the higher score, note both reporting agents.
3. Apply the filters **in order**:
   1. **Min-impact cutoff**: drop any issue with `impact < MIN_IMPACT_SCORE`.
   2. **Progressive confidence table**: drop remaining issues below the minimum confidence for their impact band — Critical (81–100) needs ≥50, High (61–80) ≥65, Medium (41–60) ≥75, Medium-Low (21–40) ≥85, Low (0–20) ≥95.
4. Drop the known false-positive classes: pre-existing issues in unchanged code; anything the compiler/typecheck/build already gates (the pipeline ran those independently before you); pedantic nitpicks a senior engineer wouldn't raise; issues explicitly silenced in code; intentional behavior changes that are the point of the diff.

## Step 6 — Outputs

**Always** — the terminal report:

```markdown
# Adversarial Review Report

**Quality Gate**: PASS / FAIL        (FAIL = any surviving critical or high issue)
**Issues**: X critical, X high, X medium, X medium-low, X low
**Min Impact Filter**: <level>   **Agents run**: <list>
**Provenance**: <np_touched> of <checked> files np-touched (run <ids>); <unmodified> unmodified since generation   ← from Step 1's np_verify_provenance; "no ledger" when the project has none

## Issues
🔴/🟠/🟡/🟢 [Severity]: <description>
**File**: `path:lines` — <evidence: what breaks and when>
<optional suggested fix>

## Improvements
<from review-code-quality, if any: description — file:location — reasoning>
```

Severity from impact: 81–100 Critical, 61–80 High, 41–60 Medium, ≤40 Low. No surviving issues → the report is the PASS block plus "checked: <agents run>".

**Pipeline mode additionally**:

1. Write the report to `<run_dir>/review-report.md`.
2. `np_write_handoff(handoff_dir, "review-findings-ext.json", {...})` — same inner shape as `review-findings.json` (the code-review-conventions schema):

```json
{
  "agent": "np-review",
  "files_reviewed": 12,
  "quality_gate": "PASS",
  "findings": [
    { "file": "relative/path", "line": "42-48", "rule_id": "EXT-BUG",
      "severity": "Critical|High|Medium|Low", "summary": "one-line issue",
      "suggested_fix": "..." }
  ],
  "rule_frequency": { "EXT-BUG": 3 },
  "provenance": { "checked": 6, "np_touched": 5, "unmodified": 4, "runs": ["<run_id>"] },   // additive; Step 1's np_verify_provenance summary
  "context_findings": [
    { "topic": "ext-<pattern-kebab>", "kind": "lesson",
      "claim": "<pattern> recurs across this change — <what to do instead>",
      "evidence": ["file:line", "file:line"], "supersedes": null,
      "confidence": "observed" }
  ]
}
```

- `rule_id` namespace by source agent: `EXT-BUG` (bug-hunter), `EXT-SEC` (security), `EXT-QUALITY`, `EXT-CONTRACT`, `EXT-TEST`, `EXT-HISTORY` — disjoint from conventions rule ids and the A–F standard categories.
- `context_findings`: one entry per **pattern flagged ≥2 times** (same bar as code-review-conventions); topics ALWAYS `ext-` prefixed so they never collide with `convention-*` topics. Single-occurrence issues are report rows, never lessons. No qualifying pattern → `"context_findings": []` (write the file anyway).

## Step 7 — Contract §8.1

Never spawn the `context-updater` and never write context entries yourself — the pipeline caller owns the end of the session. Standalone mode without a handoff dir: terminal report only, no findings file, no run dir.

## DO NOT

- Review outside the passed scope, or widen a patch/implement review to the whole repo.
- Fail or block the calling pipeline: reviewer-agent failures degrade to a warning; a FAIL quality gate is information for the dev, never an automatic revert or a run failure.
- Re-check project conventions — `code-review-conventions` owns `conventions.md`.
- Emit `context_findings` topics without the `ext-` prefix, entries for single-occurrence issues, or haiku scorer agents when ≤10 issues survive.
- Spawn background agents, more than 6 reviewers, or a second retry of a failed reviewer.
