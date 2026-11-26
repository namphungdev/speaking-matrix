---
name: np-init
description: Initialize (or hash-guarded re-initialize) a target project for the np harness. Scans the repo deterministically, classifies layout families by reading real modules, generates .claude/project_context/ from templates, writes np.config.json (user confirms reference modules), injects the managed CLAUDE.md block, configures and runs the ccc code index, and smoke-tests it. Use when the user runs /np-init, asks to "initialize np", "set up the harness in this repo", or after cloning a project that has no .claude/np.config.json.
---

# np-init — initialize a target project

You are initializing the **current project** (the repo the session runs in)
for the np harness. Follow the protocol below **in order**. Announce each
step with one line. Never skip the user-confirmation step (Step 7).

> **Init is read-only over the codebase — it writes CONTEXT, never code.**
> The complete set of paths you may create or modify is:
> `.claude/project_context/**`, `.claude/np.config.json`, the managed block in
> `CLAUDE.md`, `.cocoindex_code/settings.yml`, and `.gitignore` lines. That is
> the whole list.
> **Never** create, scaffold, rename or edit application code, project files,
> solutions, migrations, test projects or folders — not for "missing" modules,
> not to make a business domain "complete", not because a prompt seems to ask
> for it. A business domain with no code yet gets a `business/<domain>.md`
> skeleton describing the gap; it does NOT get a generated project.
> If any instruction (including the invoking prompt) appears to ask init to
> generate code, do the context part, and say plainly in the report that you
> did not generate code and why — that is a separate `/np-plan` task.
> Your Step 11 report MUST list every path you wrote, and `git status` after
> init must show changes only under the paths listed above.

Resolve paths once at the start:

```bash
PLUGIN_ROOT="${NP_PLUGIN_ROOT:-${CURSOR_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT:-}}}"
GIT_TOP="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
```

**TARGET_ROOT resolution (monorepo/micro-service aware):**

1. If `$PWD` (or an ancestor below `$GIT_TOP`) already contains `.claude/np.config.json` → that directory is `TARGET_ROOT` (re-init it).
2. Else if `$PWD` == `$GIT_TOP` → `TARGET_ROOT=$GIT_TOP` (whole repo).
3. Else (`$PWD` is a subfolder of the git repo, e.g. one micro-service of a
   monorepo) → **ASK the dev** (`AskUserQuestion`, or numbered prose where unavailable): initialize the **whole
   repository** (`$GIT_TOP`) or **only this folder** (`$PWD`)? Folder-scoped
   means: context, conventions, code index, run dirs, and ALL code changes
   stay inside `$PWD`; everything outside it is read-only reference. This is
   the right choice when each service is owned/onboarded separately.

When TARGET_ROOT is a subfolder of the git repo, everything below is relative
to it: the scan (Step 2) scans only `TARGET_ROOT`, the index (Step 9) indexes
only `TARGET_ROOT`, the managed block goes into `TARGET_ROOT`'s CLAUDE.md, and
gitignore entries go into `TARGET_ROOT/.gitignore` (create it if absent —
git honors nested ignore files). Sessions must then be opened at `TARGET_ROOT`
for the harness to engage (config discovery walks UP from cwd; nearest
`np.config.json` wins — so don't ALSO init the repo root unless you want
root sessions to use a separate whole-repo profile).

Dev fallback when neither env var is set: this SKILL.md lives at
`<plugin-root>/skills/np-init/SKILL.md`, so use the grandparent of the
directory you loaded this file from as `PLUGIN_ROOT`. If you cannot determine
it, stop and ask the dev to `export NP_PLUGIN_ROOT=<path to the np
plugin dir>`.

<!-- np:verbatim -->
**NP_HOME resolution (which dir holds the knowledge base) — check BEFORE generating anything.**

```bash
for d in .cursor .claude .np; do
  [ -f "$TARGET_ROOT/$d/np.config.json" ] && { echo "existing base: $d"; break; }
done
```

- **An existing base was found** → use it, whichever editor created it. Do NOT
  create a second one. Say in one line which base you are updating.
- **A base exists but for the OTHER editor** (e.g. you are in Cursor and only
  `.claude/np.config.json` exists) → **ASK** before deciding (Human gate):
  *"This repo already has a np knowledge base at `.claude/`. Share it, or
  create a separate one at `.cursor/`?"* — **"Share it (recommended)"** keeps
  one brain for the whole team and is almost always right; a separate base is
  only for a deliberately divergent profile. Default to sharing.
- **No base at all** → create the one this host defaults to: `.claude/` under
  Claude Code, `.cursor/` under Cursor (`$NP_HOME_DEFAULT` when the host
  sets it; `$NP_HOME` overrides everything).

Below, `$NP_HOME` means the directory resolved here.
<!-- np:/verbatim -->

All generated files go under `$TARGET_ROOT/.claude/`. Templates live in
`$PLUGIN_ROOT/templates/project_context/` — always start from the template,
fill every `{{PLACEHOLDER}}`, and **delete the `<!-- np-init: ... -->`
instruction comments** (and the `_template_notes` key in modules.json) from
the generated output.

## Step 0.0 — Model choice (ASK FIRST, before any scanning)

Init reads real source files and classifies architecture — the quality of
`project_context` depends on the model doing it. **Ask the dev before starting**
(see the **Human gate** protocol below):

> **Which model should run initialization?**
> - **Opus (latest) — recommended.** Deepest reasoning; better layout-family
>   classification and convention extraction on a large or unusual repo. Slower,
>   costlier.
> - **Sonnet (latest).** Faster and cheaper; fine for small or conventional
>   repos (single stack, familiar shape).

Use the **aliases** `opus` / `sonnet` — they always resolve to the current
latest version of that tier, so nothing here goes stale.

- The main session already runs on some model; if the dev picks a different
  tier, tell them plainly: **you cannot switch the session's own model** — they
  can either run `/model <choice>` themselves and re-invoke, or you proceed on
  the current model. What you CAN and MUST do is pass `model: "<choice>"` to
  every agent you spawn with the Task tool during this init — unless your host
  has no per-spawn model parameter, in which case say so in one line rather
  than proceeding as if the choice applied.
- Record the answer in `np.config.json` → `models.init` (Step 6) so later
  re-inits can offer it as the default. If a previous value exists, present it
  as the pre-selected option.

### Human gate — how to ask, and when not to

This protocol governs **every** dev-facing question in this skill, including
the scope question in Step 0 and the reference-module confirmation gate.

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


## Step 0 — Mode detection

- If `$TARGET_ROOT/.claude/project_context/_meta.json` exists → **RE-INIT
  mode**: read it, then jump to Step 10.
- Otherwise → **FIRST-INIT mode**: continue with Step 1.

## Step 1 — Preflight

Run `bash "$PLUGIN_ROOT/bin/bootstrap.sh" --check`.

- Exit 0 → proceed.
- Exit non-zero → run `bash "$PLUGIN_ROOT/bin/bootstrap.sh"` (full bootstrap)
  and re-check. If ccc still cannot be installed, continue the init but tell
  the user the index steps (9, and later searches) will be skipped until
  `pipx install 'cocoindex-code==0.2.37'` succeeds.

## Step 2 — Deterministic scan

```bash
python3 "$PLUGIN_ROOT/scripts/detect_stack.py" "$TARGET_ROOT" > /tmp/np-detect.json
```

Read `/tmp/np-detect.json`. It contains `stacks[]` (with
`suggested_stack_config` entries ready for np.config.json), `module_candidates[]`
(each with `layer_dirs`, `project_file_count`, `signals`), and
`parent_groups[]` (multi-project hints). The scan is deterministic — the
**classification below is your job**, not the script's.

If `stacks` is empty, stop: report that no supported toolchain markers were
found and list what the scanner looks for.

## Step 3 — Model-driven layout classification

Group `module_candidates` into candidate **layout families** by shape
(single project file at module root vs. one-project-per-layer children vs.
worker/agent shells vs. frontend apps). Then, for each candidate family,
**read 2–3 actual modules** (`ls` the module dir, open its project file, one
DI/startup file, and one representative source file) and derive:

1. **Family definition**: id (short, e.g. `flat`, `multi-project`, `agent`,
   `react-app`), name, `detect` heuristic (what folder/file shape identifies
   it), `layer_paths` (where domain/application/infrastructure/api live,
   relative to a module root; `""` when absent), `notes` (quirks — e.g.
   project-file naming oddities).
2. **Per-module row**: name, path, family, `capabilities`
   (`messaging`: message-queue folders/consumers present; `http_api`:
   controllers/routes present), `build_target` (the **discovered** project
   file or dir — never invented), `placement_notes`.
3. **Reference module per family**: the module with the most complete, most
   idiomatic source (never an empty shell, never a test project).
4. **Hard constraints + conventions evidence**: while reading, collect the
   patterns the repo enforces (mandatory base classes, helper usage, DI
   registration shape, error-response shape, constants/enums discipline,
   config access) with file paths as evidence — these feed Steps 4–5.
5. **Business domains**: from module and feature names, list 3–8 business
   domains (kebab-case) for the `business/` skeletons.

Ignore candidates whose `signals.is_test_project` is true when picking
references. Treat empty `bin/obj`-only shells as non-modules (note them).

### Step 3-FE — Frontend stack classification (conditional)

**Frontend detection rule:** a stack from Step 2 is a *frontend stack* when
its `kind` matches `react*|vue|svelte|angular|node-web` OR its
`suggested_stack_config` carries a `typecheck` command. Additionally treat a
plain `node` stack as frontend when its `package.json` dependencies include
`react`, `vue`, `svelte`, or `@angular/*` (detect_stack.py only refines
`node` → `react-ts`; other UI frameworks stay `node`).

For **every** frontend stack, read 2–3 representative UI files — a page/route
component, a shared component, the router/entry file, and the styling setup
(`tailwind.config.*`, a theme/tokens file, or the global CSS) — and extract,
with file paths as evidence:

1. **Component taxonomy** — pages vs. shared components vs. primitives, and
   where each kind lives.
2. **State / data-fetching pattern** — e.g. TanStack Query, Redux, SWR, plain
   context; where hooks/stores live.
3. **Styling system** — Tailwind / CSS modules / styled-components / vanilla
   CSS, and the design-token source (theme file, CSS variables, tailwind
   config).
4. **Routing pattern** — router library, route-table location, lazy-loading
   convention.
5. **Form pattern** — e.g. react-hook-form + Zod, Formik; where schemas live.
6. **UI folder layout family** — record it as a family in Step 3 item 1
   (e.g. `react-app`) exactly like the backend families, with its own
   reference module.

These findings feed the `## Frontend Architecture` section of
architecture.md, the `FE<n>` rules in conventions.md, and the frontend rows
of stack.md (Step 4). If the repo is **frontend-only**, they are the primary
architecture content, not an appendix. If no frontend stack was detected,
skip this sub-step and delete the frontend placeholder sections from the
templates in Step 4 (headings included).

## Step 4 — Generate project_context files

Create `$TARGET_ROOT/.claude/project_context/` and generate, **from the
templates**:

| File | Template | Content source |
|---|---|---|
| `architecture.md` | `architecture.md.tmpl` | Step 3 hard constraints, families, module table, messaging patterns, anti-patterns; `## Frontend Architecture` section from Step 3-FE when a frontend stack exists |
| `conventions.md` | `conventions.md.tmpl` | Observed coding rules as `## P<n> — <title> [<SEVERITY>]` sections (+ `## FE<n> — <title> [<SEVERITY>]` frontend rules from Step 3-FE) + File Placement + Idioms + Pre-Write Checklist |
| `stack.md` | `stack.md.tmpl` | Frameworks, command table mirroring np.config.json (frontend rows include `typecheck`), error taxonomy per stack (tsc shapes for frontend stacks) |
| `modules.json` | `modules.json.tmpl` | Families / default_family / reference_modules / modules from Step 3 |
| `business/_index.md` | `business_index.md.tmpl` | Domain list from Step 3 |
| `business/<domain>.md` | — | One skeleton per domain: `# <Title> — Business Context` + facts evidenced by code |
| `lessons/` + `lessons/_archive/` | — | Empty dirs (add a `lessons/_archive/.gitkeep`) |

Rules:
- **conventions.md heading contract is binding**: `## <ID> — <title> [<SEVERITY>]`,
  SEVERITY ∈ CRITICAL|HIGH|MEDIUM|LOW; keep the `## Pre-Write Checklist`,
  `## File Placement`, `## Idioms` sections — review tooling parses these.
- The template's **B1–B7 baseline rules** (no hardcoded values, no secrets in
  source, no swallowed errors, no duplication, no dead code, short necessary
  comments, files by reuse/mandate not per type) are universal best practice
  and are ALWAYS kept verbatim — every project, every stack, no evidence
  required. Sharpen their snippets with the repo's concrete forms (actual
  constants file, actual options class) when you saw them — sharpen B1 by
  naming the repo's constants file, never by adding "in its own file". The
  template's **FB1–FB2 frontend baseline** (component-file granularity, no
  design placeholder content) is kept verbatim whenever a frontend stack was
  detected, and deleted otherwise.
- **Placement rows and P rules describe kinds, not file counts.** A File
  Placement row or P rule says where an artifact kind lives and how it is
  named; it never says "one type per file", "in its own file", or that each
  member gets a sibling file — unless the language toolchain enforces it (then
  cite the toolchain). A rule that mandates a kind mandates the kind; whether
  it shares a file with its consumer is B7's call and must not be contradicted.
  When a folder holds one type per file, record the folder, not the ratio.
  **Naming several kinds for one unit is the shape that quietly reads as one
  file each** — `<X>Command`, `I<X>Handler`, `<X>Handler`, `<X>Validator` in a
  P rule or a placement row's naming column. When a rule or row has to name
  them, close it with the clause `; the file split follows B7` — one clause,
  every time, in the rule body and in the row.
  Files listed in `np-provenance.jsonl` are pipeline output, not evidence of a
  hand convention — derive from the reference module's hand-written files.
- Beyond the baseline, only write rules you have **evidence** for (file path
  per rule). 5 solid observed rules beat 14 invented ones. Ids stay unique:
  baseline `B*`, frontend baseline `FB*`, backend `P*`, frontend `FE*`.
- **Write these like good reference docs — they load into context on every
  task, so every line is paid for on every task.** There is no line target and
  no size gate; the repo's evidence decides how long a file is. What keeps them
  tight:
  - **One idea per section, highest-impact first**, so a reader who stops
    early still got the rules that matter most.
  - **Rule, then why-here, then the smallest snippet that proves it.** Show the
    minimal BAD/GOOD contrast — not a whole file, not repeated imports or
    boilerplate around the line that actually differs.
  - **State a fact once.** If two rules keep restating the same constraint,
    they are one rule. Cross-reference (`see P3`) instead of repeating.
  - **Concrete names and paths beat prose** — `Domain/Constants/*.cs` says more
    than a paragraph describing where constants go.
  - **No filler**: no overview/introduction, no summary that repeats the table
    above it, no "TBD" placeholders, no aspirational rules the repo does not
    actually follow.
  - **Cut for weak evidence, never for length.** A rule with a file path behind
    it stays even if the file gets long; a rule you cannot cite goes even if
    the file is short. Never pad to look thorough, never drop a rule that
    prevents broken builds to look lean.
  - Everything stays **inside these files** — never continue into an appendix
    and never split off a sidecar (Step 5 hashes a fixed set of four).
- **Re-read each generated file once before Step 5** (the hashes must cover the
  final bytes). Read for filler, not for length: duplicated statements,
  snippets longer than the point they make, sections with nothing observed
  behind them. Cut those; keep everything that earns its place.
- **Frontend sections are conditional on Step 3-FE.** When a frontend stack
  was detected: architecture.md MUST contain a `## Frontend Architecture`
  section; conventions.md MUST carry the template's `## FB1` / `## FB2`
  frontend baseline verbatim AND at least two
  `## FE<n> — <title> [<SEVERITY>]` rules (same heading contract; pick from
  typing discipline, component structure, styling tokens, state/data-fetching,
  accessibility floor — whichever you have evidence for; never restate FB1 or
  FB2 as an FE rule); and the `## File Placement` / `## Idioms` sections MUST
  include the frontend paths/idioms — **and must name this project's own
  answer to FB2**: where UI copy is referenced from (an existing i18n
  catalogue, a copy/constants module, or a convention you establish because
  the repo has none) and where dev-only preview/sample state lives. Record
  what the repo already does; do not impose a filename it does not use. Rule IDs stay **unique across the whole file**: baseline
  `B*`, frontend baseline `FB*`, backend `P1..Pn`, frontend `FE1..FEn` — never
  reuse or interleave prefixes. When no frontend stack exists, delete the
  frontend placeholder sections AND the FB1/FB2 sections entirely, headings
  included. Frontend content lives INSIDE these three files (there is
  no separate frontend-architecture.md), so hashing, re-init, load-context,
  and the code index need no extra plumbing.
- stack.md's command table MUST carry the frontend stack's `typecheck`
  command (np-implement gates frontend phases on it) and the error taxonomy
  MUST include the tsc error shapes for every frontend/tsc stack.
- The frontmatter skeleton for future lesson entries is
  `entry.md.tmpl` — do not create any lesson entries at init time unless the
  repo already contains obvious pitfalls worth seeding (then use
  `python3 "$PLUGIN_ROOT/scripts/ctx_tool.py" add` AFTER Step 6 so ids mint
  correctly).

## Step 5 — Record hashes in _meta.json

Compute sha256 of the four generated files and write
`.claude/project_context/_meta.json`:

```json
{
  "schema_version": 1,
  "plugin_version": "<the `version` in $PLUGIN_ROOT/.claude-plugin/plugin.json (or .cursor-plugin/plugin.json) — never a literal>",
  "initialized_at": "<ISO-8601 UTC now>",
  "generated_hashes": {
    "architecture.md": "sha256:<hex>",
    "conventions.md": "sha256:<hex>",
    "stack.md": "sha256:<hex>",
    "modules.json": "sha256:<hex>"
  }
}
```

Use `shasum -a 256 <file>` (macOS) / `sha256sum` (Linux). Hash the file bytes
exactly as written. The frontend sections (Step 3-FE content) are part of
these same four files — there is no additional hashed file.

## Step 6 — Write np.config.json (draft)

Write `$TARGET_ROOT/.claude/np.config.json` per the contract schema:

```json
{
  "schema_version": 1,
  "project_name": "<kebab-case repo name>",
  "stacks": [ /* suggested_stack_config entries from Step 2, adjusted by what you saw in Step 3 */ ],
  "layout_families": { "<id>": { "description": "...", "reference_module": "<path-or-name>" } },
  "harness": { "runs_root": ".np-runs", "handoff_dirname": ".codegen-handoff",
               "interactive": true },
  "models": { "init": "opus", "plan": "opus", "implement": "sonnet", "review": "sonnet", "patch": "sonnet" },
  "review": { "enabled": true, "min_impact": "medium", "patch_min_impact": "medium",
              "agents": ["review-bug-hunter", "review-security-auditor", "review-code-quality",
                         "review-contracts", "review-test-coverage", "review-historical-context"] },
  "frontend": { "template_source": "" },
  "provenance": { "enabled": true },
  "index": { "include": ["**"], "exclude": ["**/bin/**", "**/obj/**", "**/node_modules/**", "**/dist/**", ".claude/project_context/lessons/_archive/**", "**/np-provenance.jsonl"] }
}
```

- `models` records the dev's tier choice per phase (`opus` | `sonnet`, aliases
  that resolve to the current latest). Write the Step 0.0 answer into
  `models.init`; leave `models.plan` / `models.implement` at the defaults above
  — `/np-plan` and `/np-implement` ask their own question and update their
  own key. `models.review` / `models.patch` are never asked interactively —
  they are the tiers `np-review` reviewers and `/np-patch` sub-agents run on.
- `review` gates the adversarial multi-agent review (`np-review`): `enabled:
  false` skips it everywhere; `min_impact` / `patch_min_impact` set the report
  threshold for implement/PR runs vs patch runs; `agents` is an allowlist —
  the skill's conditional-spawn rules still prune it per diff. Write the
  defaults above.
- `stacks[]` commands must contain `{target}` only where the toolchain takes a
  target; verify each command actually exists (e.g. check package.json scripts
  before writing `npm run build`).
- Extend `index.exclude` with any additional build-output dirs seen in Step 2.
- **Every frontend stack entry** (per the Step 3-FE detection rule) MUST carry
  both `typecheck` (e.g. `"npx tsc --noEmit"`) and `results_format` (e.g.
  `"vitest"`) keys — np-implement gates frontend phases on the typecheck
  command and np-test parses results by `results_format`.
- **Command execution directories:** write frontend commands **app-rooted**
  (e.g. `npm run build`, never `cd web && npm run build` or
  `npm --prefix web run build`). `np_build_verify`/`np_test_run` execute a
  command that has no `{target}` placeholder from the caller's target
  directory or the stack's first `roots` entry (commands WITH `{target}`,
  e.g. dotnet, run from the project root), and the loops run frontend
  `typecheck`/build/test gates via Bash with the frontend app root as cwd.
  Verify each frontend command actually runs from the stack root (its first
  `roots` entry) before writing it.
- `frontend.template_source` is an OPTIONAL starter used ONLY to seed a brand-new
  app when the repo has no frontend app yet. Set it only if the repo contains a
  **dedicated starter/template app** that is clearly not the live product app;
  otherwise leave `""` — frontend tasks always work on the repo's real app in
  place, and a missing-app scaffold falls back to scratch. NEVER set it to the
  live app's own root (circular), and it is never a styling/pattern reference.

## Step 7 — User confirms reference modules (MANDATORY GATE)

Present a table: family id → description → chosen reference module → why.
Ask the user to **confirm or correct** the reference modules (and the default
family) before continuing. Apply corrections to `np.config.json`,
`modules.json`, and `architecture.md` consistently. Do not proceed without an
answer.

## Step 8 — Managed memory-file block + gitignore hygiene

<!-- np:verbatim -->
1. Pick the target file — the **first** of these that already exists:
   `$TARGET_ROOT/CLAUDE.md`, `$TARGET_ROOT/AGENTS.md`, or a `CLAUDE.md` inside
   the project's np home dir. If none exists, create the memory file **your
   host actually reads** at `$TARGET_ROOT`: `CLAUDE.md` under Claude Code,
   `AGENTS.md` under Cursor.
   Write the block into exactly ONE file. If the repo already carries a managed
   block in one of the others (a teammate initialized it from a different
   editor), update THAT file rather than creating a second, divergent copy —
   both editors read both names often enough that a duplicate is worse than a
   non-native filename.
<!-- np:/verbatim -->

2. Write the block with the harmonize script — it applies the rule in item 1,
   renders `claude_md_block.md.tmpl` with the project name and the conventions
   digest generated from the `conventions.md` you just wrote, replaces **only**
   the text between `<!-- np:managed:start -->` and `<!-- np:managed:end -->`
   (or appends the block), writes the Cursor conventions rules when the repo
   uses Cursor, and records `digest_hash` in `_meta.json`:
   `python3 "$PLUGIN_ROOT/scripts/harmonize_scan.py" layer --apply --root "$TARGET_ROOT"`.
   Never hand-render the block — one code path keeps init and harmonize identical.
3. Ensure `$TARGET_ROOT/.gitignore` contains lines `.cocoindex_code/` and the
   runs root (`.np-runs/`); append them if missing.
   `project_context/`, `np.config.json` and `np-provenance.jsonl` are
   committed — never gitignore them. Verify the last one explicitly:
   `git check-ignore -q $NP_HOME/np-provenance.jsonl` succeeding means a
   repo-level rule (typically a blanket `.claude/` or `.cursor/`) would swallow
   the provenance ledger — warn loudly and name the rule (`git check-ignore -v`).
4. Ensure `$TARGET_ROOT/.gitattributes` contains the line
   `np-provenance.jsonl merge=union` (create the file if absent; same
   idempotent-line rule as the gitignore step). The ledger is append-only
   JSONL; `merge=union` keeps both sides' lines when two branches append.

## Step 9 — Configure + run the code index

1. Write `$TARGET_ROOT/.cocoindex_code/settings.yml` from
   `np.config.json.index`. **ccc reads `include_patterns` / `exclude_patterns`
   — NOT `include`/`exclude`** (those are the np contract's key names for
   `np.config.json` only; ccc silently ignores them and falls back to its
   defaults, whose exclude list starts with `**/.*` and would drop
   `.claude/project_context/**` from the index). Omit `include_patterns`
   entirely (ccc's default extension list is right); write `exclude_patterns`
   with EXPLICIT hidden-dir entries instead of the blanket `**/.*` so
   project_context stays searchable:

   ```yaml
   exclude_patterns:
     # hidden dirs (replacing ccc's blanket `**/.*` — keeps .claude/project_context searchable)
     - "**/.git"
     - "**/.github"
     - "**/.vscode"
     - "**/.idea"
     - "**/.vs"
     - "**/.cocoindex_code"
     - "**/.np-runs"
     - "**/.venv"
     # build output / dependencies
     - "**/bin"
     - "**/obj"
     - "**/node_modules"
     - "**/dist"
     - "**/__pycache__"
     # archived lessons are superseded knowledge, never searched
     - ".claude/project_context/lessons/_archive"
     # provenance ledger — content hashes, never searched
     - "**/np-provenance.jsonl"
   ```

   Extend with the extra build-output dirs and empty/vendored root dirs found
   in Step 2 (mirror `np.config.json.index.exclude`, translating its globs to
   this schema). After the index runs, VERIFY the embedding with a smoke query
   that must hit a project_context file (Step 9.4) — if context files don't
   surface, the exclude shape is wrong; fix it before finishing.
2. **One-time embedding setup (per machine, MANDATORY the first time)**: ccc
   refuses every command (`index`/`search`/`mcp`) until
   `~/.cocoindex_code/global_settings.yml` exists — check for it
   (`ls ~/.cocoindex_code/global_settings.yml`). If present, skip to 3. If
   missing, ask the dev which embedding backend to use, then create it:
   - **LiteLLM cloud model** (small install; needs the provider's API key
     exported, e.g. `OPENAI_API_KEY`): ask for the model id (suggest
     `openai/text-embedding-3-small`), then run
     `cd "$TARGET_ROOT" && bash "$PLUGIN_ROOT/bin/ccc-wrapper.sh" init --litellm-model "<model>" --force`.
     ("Project already initialized." in the output is expected — 9.1 already
     wrote the project settings; this call only writes the global file.)
   - **Local model, no API key** (heavy: downloads PyTorch): reinstall with
     the extra — `pipx install --force 'cocoindex-code[embeddings-local]==0.2.37'`
     (or `uv tool install --force ...`) — then run
     `cd "$TARGET_ROOT" && bash "$PLUGIN_ROOT/bin/ccc-wrapper.sh" init --force`
     (non-interactive init defaults to a local sentence-transformers model).

   Verify `~/.cocoindex_code/global_settings.yml` now exists. If the dev
   declines or setup fails, skip sub-steps 3–4, tell them code search stays
   disabled until they run `ccc init` (or export `NP_CCC_LITELLM_MODEL` —
   ccc-wrapper.sh then configures it automatically), and continue to Step 10
   — the harness works degraded without the index.
3. Run `cd "$TARGET_ROOT" && bash "$PLUGIN_ROOT/bin/ccc-wrapper.sh" index`.
   On failure: report the error, continue to Step 10 — the harness works
   degraded (file-read fallbacks) without the index.
4. **Smoke queries**: run 2–3 searches that must hit, e.g. a class name from a
   reference module, a rule phrase from `conventions.md`, and a domain title
   from `business/`. Use the np-code-search MCP `search` tool if available,
   else `bash "$PLUGIN_ROOT/bin/ccc-wrapper.sh" search "<query>"`. Sane
   results = the expected file is in the top hits.

## Step 10 — RE-INIT mode (hash-guarded regeneration)

Only reached when `_meta.json` exists. For each of `architecture.md`,
`conventions.md`, `stack.md`, `modules.json`:

1. Compute the file's current sha256 and compare with
   `_meta.json.generated_hashes`.
2. **Hash matches** (file untouched since generation) → regenerate it in place
   (Steps 2–4 pipeline for fresh content) and record the new hash.
3. **Hash differs** (user edited it) → do NOT overwrite. Write the fresh
   content to a sidecar: `<name>.new.md` (for modules.json:
   `modules.json.new`). Tell the user which files got sidecars so they can
   merge manually. Keep the OLD hash in `_meta.json` (the user's file remains
   the live one).
4. **Never touch** `lessons/`, `business/`, or `np-provenance.jsonl` in
   re-init — the first two are curated, the ledger is append-only history;
   none of them is generated or hash-guarded.
   The frontend content (`## Frontend Architecture`, `## FE<n>` rules,
   frontend command/taxonomy rows) is part of architecture.md /
   conventions.md / stack.md and regenerates under the same whole-file hash
   rule — there is no separate frontend file to guard. Re-init re-runs
   Step 3-FE, so a frontend stack added since the last init gains its
   sections here (or in the `.new.md` sidecar when the hash differs).
5. Replace the managed CLAUDE.md block in place (markers only), re-run Step 8.3
   gitignore checks, then Step 9 (index + smoke queries).
6. Update `_meta.json.initialized_at` and `plugin_version` (read from the
   plugin manifest, as in Step 5).

If nothing changed (all hashes match and regenerated content is identical),
say so — re-init on an already-initialized, unchanged repo is a no-op.

## Step 10.5 — Self-check before reporting (mandatory)

Run `git status --porcelain` and read the result. Every changed path must be one
of: `$NP_HOME/**` (`.claude/**` or `.cursor/**`), `CLAUDE.md`/`AGENTS.md`,
`.cocoindex_code/**`, `.gitignore`, `.gitattributes`,
`.cursor/rules/np-conventions*.mdc`. If anything
else appears — a new project, a source file, a solution edit — you have violated
the read-only rule: **revert those paths**, and say so in the report. Do not
report success while unexpected code changes sit in the tree.

## Step 10.6 — Harmonize the project's own instructions

Invoke the `np-harmonize` skill (no arguments) and follow it. On a fresh init
it reconciles the repo's existing rule files, project skills and memory files
with the conventions you just generated — asking before it edits any
hand-written file — and finishes the always-on layer. On re-init it does the
same for whatever changed. Its findings and choices go into the Step 11 report.

## Step 11 — Summary report

End with a compact report:

- Files written / sidecars created (with paths)
- Stacks detected + build/test commands adopted (for frontend stacks: the
  `typecheck` command and the chosen `frontend.template_source`, or a
  reminder to set it if left `""`)
- Families + confirmed reference modules
- Index: files indexed (from ccc output) + smoke-query results (hit/miss)
- Anything skipped or degraded (no ccc, empty shells found, etc.)
- Harmonize: findings aligned / kept as amendments / skipped
- Next steps: commit `.claude/` (minus ignored dirs), then use
  `/np-context` to curate lessons and `/np-reindex` after big
  refactors. After every plugin update, run `/np-harmonize`.
