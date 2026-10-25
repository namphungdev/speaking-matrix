---
name: writing-plans
description: Use when you have a spec or requirements for a multi-step task, before touching code
---

# Writing Plans Skill

## Overview

Write comprehensive, step-by-step implementation plans for an engineer or AI Agent who has not seen this codebase or this spec. Assume they write idiomatic code in the project's language once they know the exact interface, file structure, and tests. What they cannot know is what you decided: which files, which names and signatures, which values from the spec, which tests prove each task. Document those. Give them the whole plan as bite-sized tasks. Keep code DRY and YAGNI.

**Announce at start:** "I'm using the writing-plans skill to create the implementation plan."

**Save plans to:** `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md`
*(Example: `docs/superpowers/plans/2026-10-23-flashcard-3d.md`)*

---

## Scope Check & Preparation

1. **Spec & Architecture Review:**
   - For `apps/web` tasks, read and analyze the master living design file at `apps/web/specs/prototype.html` as well as repository rules in `AGENTS.md` and `apps/web/AGENTS.md`.
   - If the request covers multiple independent subsystems (e.g., both Frontend Web and Backend API), suggest breaking it into separate plans — one per subsystem.

2. **File Structure Mapping:**
   Before defining tasks, map out which files under `apps/web/src/` will be created or modified and what each file is responsible for:
   - Design units with clear boundaries and well-defined interfaces.
   - Prefer smaller, focused React components/hooks over large files that do too much.
   - Files that change together should live together. Split by responsibility, not by technical layer.

---

## Plan Document Header Format

Every plan file saved to `docs/superpowers/plans/YYYY-MM-DD-<feature-name>.md` **MUST** start with this exact header:

```markdown
# [Feature Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `@executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences describing the technical approach and component hierarchy]

**Tech Stack:** React.js, Vite, Tailwind CSS, Lucide Icons, Web Speech API

**Living Spec:** `apps/web/specs/prototype.html`

## Global Constraints
- Strictly maintain mobile-first responsive constraints matching `apps/web/specs/prototype.html`.
- Use Tailwind CSS utility classes. Avoid raw inline CSS except for dynamic CSS variables or 3D transform properties.
- All code must pass `npm run build` inside `apps/web` without syntax or compilation errors.

## Review Focus
[List 3-5 potential failure modes or edge cases that the implementation must avoid (e.g., audio playing overlaps, broken 3D flip card transforms on iOS Safari, unhandled browser Web Speech API permissions).]

---

### Task N: [Component/Feature Name]

**Files:**
- Create: `apps/web/src/components/ExactFile.jsx`
- Modify: `apps/web/src/App.jsx`

**Interfaces:**
- Consumes: [Props, state, or hooks required from earlier tasks — exact signatures]
- Produces: [Exported components, functions, or state provided for later tasks — exact signatures]

- [ ] **Step 1: Write/Setup Component Scaffolding**
  Create the initial component file with JSX structure, export default signature, and layout matching `prototype.html`.

- [ ] **Step 2: Implement Logic & Tailwind Styling**
  Add React state management, event listeners, hook integration, and exact Tailwind classes.

- [ ] **Step 3: Verification Step**
  Run command in `apps/web`: `npm run build`
  Expected: Build succeeds with 0 errors and zero syntax/import issues.

<!-- - [ ] **Step 4: Commit**
  ```bash
  git add apps/web/src/...
  git commit -m "feat(web): implement [Component/Feature Name]"
  ``` -->

---