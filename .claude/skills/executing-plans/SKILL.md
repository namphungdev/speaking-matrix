---
name: executing-plans
description: Use when executing an implementation plan in the current session as the implementer yourself.
---

<!-- np:managed:start -->
> Project conventions in `.claude/project_context/conventions.md` apply to every file this skill writes, and win over anything below that disagrees with them. Where a rule below spells a unit out as a list of file names or artifact kinds, it names the kinds and their folder — how many files carry them follows B7, so single-use members live with their consumer.
<!-- np:managed:end -->

# Executing Plans Skill

## Overview

Execute an approved implementation plan systematically, task by task, in the current session. 

**Core Principle:** The plan already did the thinking. Execute it exactly, prove each step with build/test verifications, and leave a clear record of your progress.

**Narration:** Between tool calls, narrate at most one short line summarizing your immediate step.

**Continuous Execution:** Execute all tasks from the plan continuously. Do not pause between tasks to ask "should I continue?" unless blocked by one of the Four Stopping Triggers.

**Rulings, Not Stalls:** Conflicts, ambiguities, or plan defects must be decided on the spot using engineering judgment aligned with `apps/web/specs/prototype.html` and `AGENTS.md`. Record every decision as:
`Ruling: <what you decided> — <why> — <what it costs if wrong>`

**Four Stopping Triggers (Stop and ask ONLY for these):**
1. An irreversible or destructive operation (e.g., deleting critical project files or unrecoverable git commands).
2. A security-sensitive action (e.g., committing private API keys or credentials).
3. Side effects outside the repository workspace.
4. A plan so fundamentally broken that every path forward is a guess.

---

## Setup & Pre-flight Scan

1. **Locate Plan File:** Identify the active plan file (e.g., `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`).
2. **Read Specifications:** Read the plan completely along with `AGENTS.md`, `apps/web/AGENTS.md`, and `apps/web/specs/prototype.html`.
3. **Initialize Tracking:** Track progress task-by-task. Maintain awareness of completed vs remaining tasks in your context.

---

## The Task Execution Loop

Process each task sequentially from Task 1 to the final task:

### 1. Read Task Brief
- Read the task section in detail, noting target file paths, interfaces (Consumes/Produces), and step actions.

### 2. Work the Steps (Implement & Verify Cycle)
- Create or update the target files under `apps/web/src/`.
- Apply clean React architecture, proper hooks, and exact Tailwind CSS classes.
- **Run Verification Step:**
  Execute the verification command in the web application directory:
  ```bash
  cd apps/web && npm run build