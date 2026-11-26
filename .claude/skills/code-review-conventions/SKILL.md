---
name: code-review-conventions
description: Post-hoc code review engine. Scans source files against the project's generated conventions (rules and severities parsed at runtime from conventions.md headings) plus a standard engineering checklist, and emits REVIEW-RESULT.md with one row per violation — plus review-findings.json when run inside a pipeline handoff dir. Use AFTER code is written; for pre-write guidance invoke the conventions skill instead.
---

# Project Convention Code Review

You are a Senior Architect reviewing source code against this project's generated conventions. The rules are NOT in this skill — they live in `.claude/project_context/conventions.md` and are parsed at runtime. You must scan every in-scope file, every class, every method. Nothing may be missed.

## Step 0: Load the rule set (fail-closed)

1. Walk up from the current working directory to the nearest `.claude/np.config.json` and `.claude/project_context/conventions.md`. If either is missing, stop and tell the user: **"np not initialized — run /np-init"**.
2. Parse the rule table from `conventions.md` headings. Every rule section has the shape:

   ```
   ## <ID> — <title> [<SEVERITY>]
   ```

   Build a runtime table: `ID` (the review **category**), `title`, `SEVERITY` (Critical/High/Medium/Low — normalize case), and the rule body (what to flag, BAD/GOOD examples). Also read the `## Amendments` section if present — amendments override the rule bodies above them.

   **Seed the baseline.** The template every `conventions.md` is generated from carries universal baseline rules (`## B<n>`, and `## FB<n>` for frontend stacks) that a project initialized earlier may lack. For each baseline ID missing from the runtime table, add it from `.claude/templates/project_context/conventions.md.tmpl` with the severity in its heading (FB rules only when the review scope contains UI files). Note in the report header which IDs were seeded, so the dev knows the file is behind the template.
3. Also load `.claude/project_context/architecture.md` — its hard constraints (layering direction, mandated base classes, wiring patterns) are reviewed under the standard category `F-ORGANIZATION` at severity Critical.

## Step 1: Determine review scope

- **Explicit scope** (the user or invoking pipeline named files/a diff/a directory): review exactly that.
- **Default scope**: every source file under the roots in `np.config.json` → `stacks[].roots`, matching each stack's source extensions (infer from the stack `kind` and `stack.md`; when unsure, include anything the code index would index). Exclude build output and vendored dirs per `np.config.json` → `index.exclude`.

List the files first (e.g. `Glob`, `np_list_files`, or `find` via Bash) and record the count. If the scope is very large (>200 files), prioritize by layer: domain → application → infrastructure → presentation → shared, and say explicitly which files were not reviewed.

If the user provided a `<source-code>` block instead of a directory, read that block directly.

## Step 2: Scan

1. Read EVERY in-scope file. Record the relative path so it can appear in the result.
2. Check each file against:
   - **Every parsed project rule** from Step 0 — flag every occurrence, do not de-duplicate per file.
   - **The Standard Engineering Checklist** below (categories `A-FUNCTIONALITY` … `F-ORGANIZATION`).
   - **Layering rules** from `architecture.md` — any reverse-direction dependency is Critical under `F-ORGANIZATION`.
3. For each violation, capture: file path, line/method, specific description, category (the rule `ID` or a standard category), severity, and a concrete suggested fix.

## Step 3: Write REVIEW-RESULT.md

Write `REVIEW-RESULT.md` at the project root (or the reviewed directory's root) in exactly this structure:

```markdown
## OVERVIEW
- Total files reviewed: X
- Total issues found: X
- Distribution by severity: Critical (X) | High (X) | Medium (X) | Low (X)

## ALL ISSUES
List 100% of the issues found in FULL. Do NOT omit or summarize.

| # | File Path | Line/Method | Issue | Category | Severity | Suggested Fix |
|---|-----------|-------------|-------|----------|----------|---------------|
| 1 | src/... | Method() | Specific description | <rule ID> | Critical | Specific fix code |
| 2 | src/... | Property | Specific description | A-FUNCTIONALITY | High | Specific fix |

## ARCHITECTURE CONCERNS
General remarks on architecture, layer violations, and design compliance (against architecture.md).

## VERIFICATION CHECKLIST
- [ ] Have ALL issues been listed (Critical + High + Medium + Low)?
- [ ] Does each issue have file path, line/method, description, category, severity, suggested fix?
- [ ] Has any issue been "summarized" or merged?
- [ ] Is each suggested fix detailed enough to auto-fix?
```

**Categories** must be either a rule `ID` parsed from `conventions.md` headings, or one of the standard categories: `A-FUNCTIONALITY`, `B-PERFORMANCE`, `C-SCALABILITY`, `D-MAINTAINABILITY`, `E-DEPENDENCIES`, `F-ORGANIZATION`.

**Severity** comes from the rule's `[<SEVERITY>]` tag; for standard-checklist issues use these definitions:

- **Critical** — latent bug, security vulnerability, hardcoded value that causes crash/data corruption, serious architecture violation. Fix immediately.
- **High** — important coding-standard violation, missing abstraction, systematic convention breach. Fix within the current sprint.
- **Medium** — code smells, a missing abstraction the project's idiom calls for (a single-implementation interface is not one — B7), lacking documentation, suboptimal organization. Fix within 1–2 sprints.
- **Low** — typos, naming, minor style. Fix when there is time.

## Step 4: Emit review-findings.json (pipeline mode only)

If you were invoked with (or inside) a pipeline handoff directory, ALSO write `review-findings.json` there via `np_write_handoff(handoff_dir, "review-findings.json", {...})`:

```json
{
  "agent": "code-review-conventions",
  "files_reviewed": 12,
  "findings": [
    { "file": "relative/path", "line": "42 / MethodName()", "rule_id": "<category>",
      "severity": "Critical|High|Medium|Low", "summary": "one-line issue", "suggested_fix": "..." }
  ],
  "rule_frequency": { "<rule_id>": 3 },
  "context_findings": [
    { "topic": "<kebab-key derived from the rule + pattern>", "kind": "lesson",
      "claim": "Rule <ID> is repeatedly violated when <pattern> — <what to do instead>",
      "evidence": ["file:line", "file:line"], "supersedes": null, "confidence": "observed" }
  ]
}
```

`context_findings` (the contract §8 producer-protocol key — the `context-updater` agent reads exactly this key): one entry per rule violated **2 or more times** in this review (`rule_frequency` ≥ 2). Skip rules with a single occurrence. When not in pipeline mode, skip this step entirely.

**Topic reuse:** if `review-findings-ext.json` (the np-review adversarial engine) already exists in the handoff dir and one of your ≥2× rules covers the **same file:line issues** as one of its `context_findings` entries, reuse that entry's exact `topic` string instead of minting a `convention-<rule-id>` topic — the updater dedupes by topic only, and one merged lesson beats two near-duplicates. Otherwise keep your own topic.

## Fix-proposal principles

Every suggested fix must follow these rules. Violating any of them invalidates the fix.

1. Do NOT change business logic — only refactor structure.
2. Do NOT rename public APIs that could affect external callers.
3. Behavior before and after the fix must be identical.
4. Every magic number/string → a clearly named constant/enum per the project's conventions.
5. When moving code, ensure all callers are updated.
6. Do NOT change the database schema or migrations.
7. Do NOT add new packages unless `conventions.md` explicitly pre-approves them — state explicitly if you propose adding one.
8. Do NOT delete files — only create new ones or edit.
9. If a fix introduces a new import or wiring/DI registration, state it explicitly in the proposal.
10. A fix never adds a narrating comment or a file header (B6) — if the fix needs explaining, the explanation goes in the review row, not the code.
11. A fix never inlines a design value, label or option list into a component to make a screenshot match (FB2) — it moves the value to the copy module or the preview fixture.
12. A fix never gives a single-use type its own file or extracts a single-implementation interface to satisfy a rule (B7). A B7 violation's fix is "fold into `<consumer file>`" — principle 8 forbids deleting files, so label it REQUIRES HUMAN REVIEW.

When a fix could shift behavior (e.g. moving validation into the domain model, renaming public surface), label it **"REQUIRES HUMAN REVIEW"** and give the reason.

## Standard Engineering Checklist (A–F)

Apply these alongside the parsed project rules. They share categories `A-FUNCTIONALITY`, `B-PERFORMANCE`, `C-SCALABILITY`, `D-MAINTAINABILITY`, `E-DEPENDENCIES`, `F-ORGANIZATION`.

### A. Functionality
- Correct output across boundary/special cases; tests for critical paths.
- Explicit error handling for I/O, network, DB; error responses follow the project's error convention.
- External integrations handle auth/data/error correctly; dependency versions explicit, no conflicts.
- Async/concurrency used correctly on I/O; safe access to shared resources.
- Input validation/sanitization; authn/authz mechanisms; correct crypto.

### B. Performance
- Loops/recursion optimized; appropriate algorithm choice; efficient collection pipelines (filter → sort → take).
- No memory leaks; disposable/closable resources released properly.
- Async paths do not deadlock; no blocking calls in async context.
- No N+1 queries; correct connection pooling; eager/lazy loading used appropriately.
- Reasonable caching with invalidation/expiration; pagination/compression for APIs.

### C. Scalability
- Modular, stateless services; clear service boundaries.
- Load balancing, rate limiting, queues used correctly where the architecture prescribes them.
- DB schema + indexing optimized; read/write distribution considered.

### D. Maintainability
- The stack's standard style conventions followed; clear names; linters/analyzers respected.
- SOLID, interfaces, dependency injection used correctly where the stack idiom calls for them.
- TODO/FIXME tracked; DRY; no duplicated code.

### E. Dependencies
- Explicit dependency versions; no unused/vulnerable packages.
- Semantic versioning; compatibility verified after updates.

### F. Organization
- Logical namespace/module hierarchy mirroring the architecture.
- Single Responsibility per class/method; minimal cross-dependencies.
- Shared code in shared libraries; layering direction per `architecture.md` strictly one-way.
- Public API documentation per the stack's convention; README up-to-date.

## Final verification before writing REVIEW-RESULT.md

Self-check:
- [ ] Every in-scope source file was opened?
- [ ] Every issue gets its OWN row (no merging "12 magic numbers in this file")?
- [ ] Every row has file path, line/method, category, severity, suggested fix?
- [ ] Suggested fix is concrete enough that an automated tool could apply it?
- [ ] Severity matches the rule's tag or the standard definitions?
- [ ] Fix-principles (no schema changes, no public-API renames without review, no unapproved packages) honored?
- [ ] Pipeline mode: `review-findings.json` written with `context_findings` for every rule violated ≥2×?

Once all checked, write `REVIEW-RESULT.md` (and `review-findings.json` in pipeline mode) and report the totals back.
