---
name: conventions
description: Read the project's generated coding conventions (project_context/conventions.md) and apply them; run its Pre-Write Checklist before every file save. Invoke BEFORE writing or editing any non-trivial source file. Fails closed if the project is not initialized.
---

# Project Coding Conventions (write-time)

You are about to write or edit source code in a np-initialized project. The project-specific coding rules are NOT in this skill — they were generated at init time into `.claude/project_context/conventions.md`. This skill tells you how to load and apply them, and carries the one universal **baseline** (Step 2.5) that applies to every project regardless of when its `conventions.md` was generated.

## Procedure

### Step 1: Locate and read the conventions (fail-closed)

Walk up from the current working directory to the nearest `.claude/project_context/conventions.md` and read it IN FULL.

**If the file does not exist**: this project is not initialized. Stop and tell the user:

> np not initialized — run /np-init

Do not fall back to generic language conventions — the whole point is project-specific rules.

### Step 2: Understand the file's structure

`conventions.md` is generated with a fixed shape you can rely on:

- **Rule sections** with headings `## <ID> — <title> [<SEVERITY>]` (e.g. `## P1 — No magic numbers [CRITICAL]`). Each rule carries rationale and usually BAD/GOOD examples in the project's own stack.
- `## File Placement` — where each artifact kind (entity, enum, service, repository, handler, wiring extension, test, …) lives per layout family. This is the placement truth the planner and implementer follow.
- `## Idioms` — the project's canonical code snippets (constructor/injection shape, error-handling shape, registration shape, naming patterns). Match these over your own habits.
- `## Pre-Write Checklist` — the per-file self-check list.
- `## Amendments` (optional, at the bottom) — dev-confirmed corrections appended by the feedback loop. Amendments override the body text above them when they conflict.

### Step 2.5: Baseline — applies even if conventions.md predates it

These rules are universal, not project-specific. They ship in the template every `conventions.md` is generated from, but a project initialized before a rule existed will not have it in its file — apply them anyway. Full text with BAD/GOOD examples lives in `.claude/templates/project_context/conventions.md.tmpl` (sections `## B<n>` and `## FB<n>`); read the relevant section from there the first time you need its detail.

- **B1** — every literal with business or config meaning is a named constant, enum member, or config key; fixed value-sets are real enums.
- **B2** — no secrets, connection strings, hostnames or environment-specific values in source.
- **B3** — no error is swallowed silently: handle, log with context, or propagate.
- **B4** — search for the existing helper/pattern before writing a new one.
- **B5** — no commented-out code, unused symbols or unreachable branches left behind.
- **B6** — every comment is ≤3 lines and says *why*, not *what*; no file-header narratives, no doc comments restating a signature, never the business change that produced the code.
- **B7** — a type earns its own file by reuse (2+ consumers), by a placement rule or toolchain that mandates a file for that kind, or because its host became hard to read; otherwise it lives with its only consumer. Match the file count of the reference module's comparable unit of work. Before you create a file, name which of the three clauses earns it — if none does, the code goes in the file you are already writing. A single-use command/result/DTO/mapper/helper/validator, an interface with one implementation (unless the comparable unit has one for that kind), and a constant that belongs to an existing group file never earn one, and neither does an `Abstractions/`-style sub-folder the comparable unit does not have.

When the file you are writing is UI code (a component, view, page or screen file, whatever the project's framework calls it):

- **FB1** — a component file exists only because the piece is reused in 2+ places, owns its own state or data fetching, or its parent had become hard to read — never because it was a design frame. Single-use sections, cards, dialogs and rows stay inline in their parent.
- **FB2** — no string, value or option list visible in the design is a literal in a component. UI copy is referenced through the project's i18n or copy layer; sample values live only in a dev-only preview source the production build never imports. Follow the mechanism this project already uses — `## File Placement` and `## Idioms` name it; establish one only if the project has none.

If the project's `conventions.md` lacks any of these IDs, tell the dev **once per session** (one line: which IDs were applied from the baseline, and that `/np-init` or a manual merge will persist them) and carry on — do not stop, and do not skip the rule.

**Rules elsewhere in the repo that read as one file per type.** A per-file phrase inside a project rule or placement row ("in its own file", "one type per file") is an init-generated artifact, not a project decision — B7 supersedes it regardless of that rule's severity, while the rule's naming and location still apply. The same holds for the two shapes that never say "own file" and are the most common cause of a change landing as a folder of near-empty files:

- a unit spelled as a **list of file names** — `Features/<UseCase>/{Command.ext, I<X>Handler.ext, <X>Handler.ext, <X>Validator.ext, Abstractions/}`;
- a placement row or rule that **names three or more artifact kinds** for one unit.

Both mandate the kinds and the folder; B7 decides how many files carry them. Follow the rule's naming and location, write the single-use members into their consumer's file, and mention the conflict in the same once-per-session line so the dev can run `/np-harmonize` and fix the rule at its source.

### Step 3: Apply while writing

- Before creating a file, resolve its location via `## File Placement` — but **mirror the target module's existing substructure first**; the placement table is the fallback when the module has no matching folder yet.
- Copy the namespace/module declaration shape from a neighbor file in the same folder; docs describe the pattern, neighbors are authoritative.
- Follow `## Idioms` for the code's shape (injection, error handling, registration, naming).
- Respect every rule at its stated severity; `[CRITICAL]` rules are non-negotiable.

### Step 4: Run the Pre-Write Checklist before EVERY file save

Immediately before saving each file (Write or Edit), walk the `## Pre-Write Checklist` from `conventions.md` item by item against the content you are about to save — **and** the Step 2.5 baseline lines, whether or not the file's checklist already includes them. Fix violations before saving — not after.

If the generated file has no `## Pre-Write Checklist` section (older generation), synthesize one from the rule headings: one check per `[CRITICAL]` and `[HIGH]` rule.

## Rules

- Fail closed: missing `conventions.md` → stop with "run /np-init".
- Read the file once per session, apply it for every file you touch in that session.
- Never quote stale project rules from memory — the generated file (plus its `## Amendments`) is the only source of truth for project-specific rules. The Step 2.5 baseline is not "from memory": it is the template's universal set and applies unconditionally, on top of the file.
- Post-hoc review of already-written code is the `code-review-conventions` skill's job, not this one's.
