---
name: init-agent-guidance
description: Use when creating, auditing, or updating repository AGENTS.md files. Inspect the actual codebase, determine root and nested instruction scopes, verify technology and commands, generate consistent Markdown instructions, and validate them against repository evidence.
---

# Initialize Agent Guidance

## 1. Objective

Create accurate, concise, repository-specific AGENTS.md files that help coding agents understand:
- What the repository and its components do.
- Where relevant code and documentation live.
- Which technologies and commands are actually used.
- Which architecture, security, and integration boundaries must be preserved.
- How to verify changes and report evidence.

Do not generate generic instructions merely to fill a template.

## 2. Operating Modes

Determine the user's intended operation:

- **Initialize**: inspect the repository and create missing instruction files.
- **Audit**: inspect existing files and report missing, duplicated, stale, or conflicting guidance.
- **Update**: modify existing guidance based on repository changes or user feedback.
- **Plan only**: recommend files and section contents without writing files.

If the user's intent is unclear and the difference affects file changes, ask one concise clarification question.

Preserve useful existing guidance. Do not overwrite files wholesale before reviewing their contents.

## 3. Repository Discovery

Before drafting, inspect the repository.

1. Identify the repository root and major directories.
2. Find all existing AGENTS.md and equivalent agent instruction files relevant to the task.
3. Inspect manifests, project files, lockfiles, workspace configuration, build configuration, test configuration, and CI workflows.
4. Inspect README and architecture documentation when relevant.
5. Inspect representative source files and tests in each component that may need its own instructions.
6. Inspect .gitignore, generated-code configuration, migration folders, and code-generation scripts when relevant.
7. Identify existing conventions and canonical implementations to follow.

Use available file-search and shell tools where appropriate. Do not assume a command or file exists before checking.

Do not scan irrelevant generated directories or dependency caches exhaustively. Expand discovery only when evidence is missing.

## 4. Evidence and Confidence

For every repository-specific claim, distinguish:

- **Verified**: directly supported by current repository files or successful command output.
- **Inferred**: supported by evidence but not conclusively established.
- **Unknown**: not established from available evidence.

Only state verified facts as established repository rules.

For important inferred or unknown facts:
- Search for additional evidence.
- If still unresolved, omit the claim or mark it as requiring confirmation.
- Ask the user only when the uncertainty materially affects correctness, security, architecture, or the generated instructions.

Never invent:
- Frameworks, runtime versions, package managers, or commands.
- Architecture patterns or mandatory libraries.
- Test coverage, CI guarantees, or successful verification.
- Authentication, authorization, or data-handling behavior.

## 5. Decide File Scope

Start with one root AGENTS.md.

Add a nested AGENTS.md only when a directory has meaningful local differences, such as:
- Different development, build, or test commands.
- Different technology or implementation conventions.
- Different security or data boundaries.
- Different architecture or integration constraints.
- Enough local guidance to justify a separate instruction file.

Do not create a nested file merely because a directory exists.

Do not create intermediate AGENTS.md files unless they provide useful shared guidance for multiple descendants.

Do not assume all coding agents discover or merge nested instructions identically. Preserve standard AGENTS.md naming and, when relevant, tell the user to verify discovery behavior in their chosen tool.

## 6. Root AGENTS.md Requirements

Use the root template in references/root-agents-template.md.

The root file should prioritize:
1. Project overview.
2. Repository map.
3. Verified technology stack.
4. Verified development commands.
5. Repository-wide architecture and dependency boundaries.
6. Cross-cutting conventions.
7. Security and data boundaries.
8. Testing and verification expectations.
9. File and change constraints.
10. Documentation references.
11. Completion-report expectations.

Treat this as a menu, not a mandatory list. Omit empty or irrelevant sections.

Root instructions must be concise and apply across the repository. Link to deeper documentation instead of copying large documents or long procedures.

## 7. Nested AGENTS.md Requirements

Use references/nested-agents-template.md as the base template.

For each nested file:
1. State its scope and responsibilities.
2. Document only verified local technologies and commands.
3. Explain local structure and canonical implementations.
4. Record implementation conventions specific to that component.
5. Explain integration boundaries with other components.
6. Include relevant local security and data-handling rules.
7. Document applicable tests and verification.
8. Link to relevant local references.

Remove sections that do not apply. Do not copy root instructions unless a short reminder is necessary to prevent a high-impact mistake.

Tailor content to the actual component. For example, frontend guidance may cover UI states and accessibility, while API guidance may cover validation, authorization, contracts, and migrations when those concepts exist in the repository.

## 8. Content Quality Rules

Every instruction should do at least one of the following:
- Prevent a likely mistake.
- Clarify an architectural or implementation decision.
- Standardize a recurring workflow.
- Identify where authoritative information lives.
- Require meaningful verification.

Prefer specific and testable instructions over vague advice.

Good:
"Run the API test project associated with the changed endpoint; use the test command verified from the project configuration."

Bad:
"Always write perfect code and test everything."

Do not include:
- Temporary task-specific requirements.
- Secrets, credentials, or private tokens.
- Unsupported architectural assumptions.
- Large copied sections from README or other documentation.
- Long reusable procedures that belong in Skills.
- Rules already completely enforced by tooling, unless agents need to understand the constraint or its remediation.
- Unverified commands presented as executable facts.

## 9. Generate and Update Files

Before writing:
1. Decide the target paths.
2. Reuse the appropriate template.
3. Replace every placeholder with verified content or remove the placeholder section.
4. Use repository-relative links where possible.
5. Preserve existing useful content and minimize unrelated changes.

When updating:
- Make the smallest meaningful change.
- Remove stale claims only after checking current repository evidence.
- Avoid introducing contradictory instructions.
- Do not edit application code as part of this Skill unless the user explicitly requests it.

## 10. Validation

After drafting, check every generated or modified file.

### Structure
- Markdown headings are consistent and readable.
- No unresolved placeholders remain.
- Sections have meaningful content.
- Links and referenced paths exist where they can be checked.

### Accuracy
- Technology names and versions match repository evidence.
- Commands are defined in manifests, project files, scripts, CI, or documentation.
- Commands are not claimed to have passed unless actually executed successfully.
- Architecture statements match representative source code and tests.

### Scope
- Root guidance is repository-wide.
- Nested guidance applies to its directory and descendants.
- Nested files add local value rather than duplicating root content.
- File count is justified by actual differences.

### Consistency
- No conflicting commands or policies exist across instruction files.
- Security and authorization boundaries are clear.
- Guidance does not contradict repository tooling.
- Important rules are not merely described when automated enforcement is available and appropriate.

If practical, run Markdown/link validation or repository-specific documentation checks. Do not install new dependencies solely to validate these files without user approval.

## 11. Completion Report

Report:
- Operation performed: initialize, audit, update, or plan only.
- Files created, modified, or intentionally not created.
- Evidence sources used to identify technologies and commands.
- Validation performed and actual results.
- Important assumptions or unresolved questions.
- Recommended follow-up, such as adding a lint rule or CI check.

Never claim full verification when only static inspection was performed.