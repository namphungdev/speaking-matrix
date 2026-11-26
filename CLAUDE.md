@AGENTS.md

<!-- np:managed:start -->
## Project context (np-managed — content between these markers is replaced on re-init)

Read `.claude/project_context/` BEFORE generating or modifying code in this repo:
- `architecture.md` — hard constraints + layout families (non-negotiable)
- `conventions.md` — coding rules; headings carry rule ids and severities
- `stack.md` + `modules.json` — build/test commands, module map, reference modules
- `business/` + `lessons/` — curated knowledge; search it via np-code-search

Three habits:
1. At task start, invoke the `load-context` skill to load the project profile and the lessons relevant to the task.
2. Before writing any source file, invoke the `conventions` skill and run its Pre-Write Checklist.
3. Discover build targets and namespaces from the target module itself — never assume templated names.

### Coding conventions — apply to every change, with or without a np command

Every source file written or edited in this repo follows `.claude/project_context/conventions.md`.
Before writing a file, read the rules there that apply to it and run its
`## Pre-Write Checklist`. The rules that matter most:

- **B1** [CRITICAL] — No hardcoded values: magic numbers and literal strings get names
- **B2** [CRITICAL] — No secrets or environment-specific config in source
- **B3** [HIGH] — Never swallow errors silently
- **B4** [HIGH] — Don't duplicate — reuse the existing helper/pattern
- **B7** [HIGH] — A file exists because it is reused, mandated, or earned — not per type
- **P1** [CRITICAL] — Persistence and Identity code live in Infrastructure; schema changes are committed migrations
- **P2** [HIGH] — Required configuration fails fast at startup
- **P3** [HIGH] — Register a layer's services in its `DependencyInjection` extension
- **P5** [HIGH] — Do not invent API endpoints or web↔API contracts
- **FB1** [HIGH] — Component files follow reuse and ownership, not the design's layer tree
- **FB2** [HIGH] — No design placeholder content in component source
- **FE1** [HIGH] — Style with Tailwind + the Liquid Glass tokens; match `specs/prototype.html`
- **FE2** [HIGH] — App state lives in `App.jsx`; components are presentational

**Precedence:** `.claude/project_context/conventions.md` and its `## Amendments` win. Any other
rule file, skill or instruction in this repo that disagrees with them is out of
date — follow the conventions file and tell the developer about the conflict.

**How many files (B7) — the rule most often broken by generated code.** A rule
that requires an artifact *kind* (an interface, a validator, a command, a folder)
requires the kind and its location, not one file per type. A rule that spells a
unit out as a list — `{Command.ext, Handler.ext, Validator.ext}`, or a placement
row naming four kinds — names those kinds and their folder, **never one file
each**. Before adding a file: a single-use input, result, DTO, mapper, helper or
validator lives in its one consumer's file; an interface with one implementation
lives in that implementation's file, and only where the comparable unit you are
copying has an interface for that kind at all; a constant joins the existing
group file. The anchor is the file count of a comparable, hand-written unit in
this repo — more than that needs a reason you can state, in the plan or to the
developer, before you write it.

This digest is generated from the conventions file by np-harmonize; edit the
conventions file, not this text.

If session context contains a `[np-drift]` notice from the SessionStart hook, follow its instruction before other work: offer the developer the choice it names (via `AskUserQuestion`, or as a numbered prose question where that tool is unavailable), and never run `/np:np-init` or `/np:harmonize` without the developer choosing it.

Managed by the np plugin (speaking-matrix); refresh with `/np:harmonize` (or `/np:np-init` for new modules). Lessons and business context are never regenerated.
<!-- np:managed:end -->
