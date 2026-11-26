---
name: np-pr-review
description: PR review loop — fetch a pull request's diff and reviewer comments via the gh CLI, review changed files against the project's generated conventions, turn dev corrections and recurring reviewer themes into context findings, run the context-updater, and summarize. Asks before posting anything to GitHub.
---

# np-pr-review — Review a PR and Harvest Reviewer Knowledge

You review a pull request two ways at once: (1) mechanically, against the project's generated `conventions.md`; (2) by mining the human reviewers' comments for durable knowledge that belongs in project context.

## Step 0 — Preflight and input

1. Confirm `.claude/np.config.json` exists; read `stacks[]`, `harness.runs_root` (default `.np-runs`), `harness.handoff_dirname`. If absent, stop: "np not initialized — run /np-init".
2. The Skill args must carry a PR number or URL. If missing, ask. From a URL, extract owner/repo/number; from a bare number, use the current repo (`gh repo view --json nameWithOwner`).

## Step 1 — Fetch the PR

```bash
gh pr view <n> --json number,title,body,author,state,headRefName,headRefOid,baseRefName,files,commits
gh pr diff <n>
gh api repos/{owner}/{repo}/pulls/<n>/files --paginate --jq '.[]|{filename,sha,status,previous_filename}'   # per-file blob sha (30/page → --paginate is required)
gh api repos/{owner}/{repo}/pulls/<n>/comments --paginate     # inline review comments
gh api repos/{owner}/{repo}/pulls/<n>/reviews --paginate      # review bodies + verdicts
gh api repos/{owner}/{repo}/issues/<n>/comments --paginate    # conversation comments
```

Collect: the changed-file list, the unified diff, every human comment (author, body, path/line when inline), the per-file `{filename → sha}` map, and every `Generated-By: np/<ver> run=<id>` trailer found in `commits[].messageBody` (regex `^Generated-By:\s*np/(\S+)\s+run=(\S+)\s*$`, multiline). Ignore bot comments for the knowledge-mining step (they are not dev corrections), but keep them visible in the summary.

## Step 2 — Materialize the changed files

Create the review workspace: `handoff_dir = {runs_root}/pr-<n>/{handoff_dirname}` (`mkdir -p`). Do NOT `gh pr checkout` — never mutate the dev's working tree for a review (a PR review is read-only; materialized PR files live under the run dir, which is state, not code).

For each changed file that belongs under a configured `stacks[].roots` (skip deletions, binaries, and generated/vendored paths per `index.exclude`):

```bash
gh api repos/{owner}/{repo}/contents/<path>?ref=<headRefOid> --jq .content | base64 -d \
  > {runs_root}/pr-<n>/files/<path>        # preserve the relative path
```

### Step 2.5 — Provenance: which of these files did np write?

The plugin records every file a run touches — as git blob hashes — into the committed ledger `<np-home>/np-provenance.jsonl`. GitHub already gave you each changed file's blob `sha` in Step 1, so verification needs no content at all: a matching hash proves *this exact content came from run X, untouched*.

1. **PR-side ledger.** If `<home>/np-provenance.jsonl` is among the PR's changed files, Step 2 already materialized it — use `{runs_root}/pr-<n>/files/<home>/np-provenance.jsonl`. Otherwise fetch it at the PR head, trying `<home>` in `.claude`, `.cursor`, `.np` (a mixed team may have initialized from either editor; tolerate 404):
   ```bash
   gh api repos/{owner}/{repo}/contents/<home>/np-provenance.jsonl?ref=<headRefOid> --jq .content 2>/dev/null | base64 -d > {runs_root}/pr-<n>/ledger.jsonl
   ```
   (Empty `content` means >1 MB — fetch `gh api repos/{owner}/{repo}/git/blobs/<sha> --jq .content` with the `sha` from the contents metadata instead.)
2. **Base-branch ledger**, for "which runs does this PR carry": merge base = `gh api repos/{owner}/{repo}/compare/<baseRefName>...<headRefOid> --jq .merge_base_commit.sha`, then the same `contents?ref=<merge base>` fetch to `ledger-base.jsonl` (404 → empty). `runs_carried` = run ids present in the head ledger but not the base one.
3. **Verify**, with the Step 1 sha map so nothing is re-hashed:
   ```
   np_verify_provenance(files=<changed files minus the ledger itself, minus status "removed">,
                         ledgers=["{runs_root}/pr-<n>/ledger.jsonl"],
                         blobs={filename: sha}, root="{runs_root}/pr-<n>/files")
   ```
   A `renamed` file is verified under `filename`; if it has no record, look up `previous_filename` and report `renamed-from`. The ledger file itself is never a review row — exclude it from Steps 3 and 3.5 too.
4. **Stale-ledger detection** — this is what turns "no record" from a guess into a finding. `trailer_runs` (from Step 1's commit trailers) minus the ledger's run ids: non-empty means commits declare np runs the ledger has no entries for — the author committed code but not the ledger. Same conclusion when trailers exist but no ledger was found in any home.

Statuses are exactly the tool's: `generated-unmodified` / `generated-edited` (file did not exist at the run's baseline), `np-modified-unmodified` / `np-modified-edited` (it did; np changed it), `no-record`, `unverifiable`, `deleted`. **Never say "hand-written"** — an absent entry cannot assert authorship; it may just be an uncommitted ledger.

## Step 3 — Conventions review

Invoke the `code-review-conventions` skill with args: the materialized files directory (`{runs_root}/pr-<n>/files/`), the changed-file list, and `handoff_dir=<handoff_dir>` — running inside a pipeline handoff dir makes it emit `review-findings.json` there in addition to `REVIEW-RESULT.md`. Focus the review on the changed files only; cite rule IDs/severities as parsed from `conventions.md` headings.

## Step 3.5 — Adversarial review (config-gated)

If `np.config.json` → `review.enabled` is not false, invoke the `np-review` skill (Skill tool name `np-review`) in pipeline mode: `handoff_dir=<handoff_dir>`, scope = the materialized changed files under `{runs_root}/pr-<n>/files/` with the PR's unified diff (Step 1) as the diff source, `min_impact` = `review.min_impact`. It writes `review-findings-ext.json` into the handoff dir and `review-report.md` into the run dir. Present its issues alongside the conventions table in Step 6 — the ask-before-posting gate covers them too; `np-review` itself never posts to GitHub.

## Step 4 — Mine reviewer comments for context findings

Work through every human comment and classify:

1. **Explicit dev correction/directive** — imperative or normative statements ("don't use X, use Y", "we always route queue names through the helper", "this module has no HTTP surface"). Each becomes a finding with `confidence: "dev_confirmed"`.
2. **Recurring theme** — ≥ 2 similar comments (same rule, same mistake pattern, possibly different reviewers/files). Merge into ONE finding; `dev_confirmed` if at least one instance is an explicit statement, else `observed`.
3. **One-off local nitpick** (naming taste on one variable, typo) — no finding.

Kind mapping: coding/architecture guidance → `lesson`; a described error + its fix → `error-solution`; domain/business fact → `business_context`; wrong module metadata (family, capabilities, build target) → `correction`.

Finding shape (contract §8, exactly):

```json
{"topic": "<kebab-key>", "kind": "lesson|error-solution|business_context|correction",
 "claim": "<the durable rule/fact, kept close to the reviewer's wording>",
 "evidence": ["PR #<n> comment by @<author> on <path>:<line> — \"<quote>\"", "..."],
 "supersedes": null, "confidence": "observed|dev_confirmed"}
```

Cross-reference with Step 3: a conventions rule that the mechanical review flagged ≥ 2× AND a reviewer also commented on is a strong recurring theme — merge the evidence into one finding rather than emitting two.

**Topic-key reconciliation (required):** the `code-review-conventions` skill already wrote its own `context_findings` into `review-findings.json` (one per rule violated ≥ 2×, topic `convention-<rule-id>-...`), and — when Step 3.5 ran — `np-review` wrote `review-findings-ext.json` (topics `ext-*`). The context-updater dedupes by topic ONLY. Before finalizing your findings, read **both** files' `context_findings`; whenever one of your mined themes covers an issue either file already carries, **reuse that entry's exact `topic` string** for your finding (do not invent a parallel reviewer-derived topic) — the updater's topic-dedupe then merges them into one lesson instead of inserting duplicates. Mined themes with no counterpart keep their own topics.

## Step 5 — Write the result handoff, then apply §8.1

```
np_write_handoff(handoff_dir, "pr-review-result.json", {
  "agent": "np-pr-review",
  "pr": <n>,
  "title": "<PR title>",
  "changed_files": N,
  "violations": N,                  // row count from REVIEW-RESULT.md
  "reviewer_comments": N,           // human comments considered
  "provenance": {                   // additive, from Step 2.5 — omit only when provenance.enabled is false
    "ledger": "<home>/np-provenance.jsonl" | null,
    "runs_carried": ["<run_id>", ...],
    "files": [ {"file": "...", "status": "generated-unmodified", "run_id": "...", "stage": "implement"}, ... ],
    "counts": { "<status>": N, ... },
    "trailer_commits": N,
    "stale": false                  // true when commits declare runs the ledger lacks
  },
  "context_findings": [ ... ]
})
```

Then, per contract §8.1:

- **Final mode (the usual case — a PR review is the end of the session):** spawn the `context-updater` agent with `handoff_dir=<handoff_dir>`. It matches findings against existing entries (superseding/updating where the reviewers corrected stale knowledge) and writes `context-update-report.json`. Read the report.
- **Deferred:** args carry `defer_context_update=true`, or `np-loop` invoked you as its review stage and the task is not yet `done` — record `"context_update": "deferred"` in `pr-review-result.json` and report the pending count instead.

Either way, never write entries yourself: matching and editing entries is the sub-agent's work, kept out of this session's context.

## Step 6 — Review summary

Compose (in chat, always):

1. **Provenance** — first, because it frames everything below. A table `| file | status |` with one row per changed file (`generated by np, unmodified ✓ (run <id>, <stage>)` / `edited by np, then edited again ✎ (in this PR | earlier)` / `no record` / …), then one count line (`<N> of <M> changed files touched by np; <K> unmodified since generation. Trailer on <a>/<b> commits.`). When Step 2.5 flagged a stale ledger, open with: *"Ledger stale: commits declare np run(s) <ids> but the PR's ledger has no entries for them — the author should `git add <home>/np-provenance.jsonl` and push."* When there is neither ledger nor trailer: *"no provenance data in this PR."* Close with the legend: *"no record" = hand-written, or the ledger was not committed; a formatter run after generation reads as "edited" — that is correct, not a false alarm.*
2. **Conventions findings** — the REVIEW-RESULT.md table for changed files (rule id, severity, file:line, suggested fix), or "no violations".
3. **Reviewer themes** — each mined finding: topic, claim, who said it, how often.
4. **Context updates** — inserted/updated/superseded ids from `context-update-report.json`, or "N findings recorded, applied at the end of the run" when deferred.
5. **Verdict line** — a one-paragraph overall take on the PR (mergeable / needs work, and why).

**Then ASK the user before posting anything to GitHub.** Offer: post the summary as a PR comment (`gh pr comment <n> --body-file <file>`) — and, when the PR has np-touched files, also apply the `np-generated` label (`gh pr edit <n> --add-label np-generated`; `gh label create np-generated --color 5319E7 --description "Contains np-generated files"` once if it does not exist; a permission error skips the label silently, the comment still posts) — post nothing, or post an edited version. Only run a posting command after an explicit yes in this conversation. Default is print-only.

## DO NOT

- Post comments, reviews, approvals, or labels to GitHub without the user's explicit go-ahead in this session.
- `gh pr checkout` or otherwise mutate the local working tree.
- Turn one-off nitpicks or bot comments into context findings.
- Emit two findings for the same theme (mechanical + human) — merge the evidence.
- Invent claims beyond what reviewers actually wrote — quote them in the evidence.
- Write context entries yourself (`context_add_entry`, `context_supersede`, edits under `project_context/`) — that is the `context-updater` sub-agent's job (contract §8.1).
