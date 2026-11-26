---
name: frontend-step-gen
description: Generates a single form step component from a compact, step-scoped context package.
model: sonnet
---

# Frontend Step Generator Agent

## Harness Performance Override

When `step_context_path` is present in the handoff, these rules override conflicting
instructions below:

1. Read only the handoff request, `step_context_path`, the target feature files needed
   for writing the step (including `src/features/{name}/{name}.copy.ts` and
   `src/features/{name}/__fixtures__/{name}.preview.ts`, which you also write), and the
   two optional project-context files named in Step 1b (`conventions.md` /
   `architecture.md` — small, read at most once each). Never read aggregate
   `_figma_reference_codes.json`, `_backend_api_catalog.json`,
   `_component_registry.json`, or unrelated screen artifacts.
2. Do not call MCP tools. Resolve library/type questions from existing project files,
   installed package types, and local error output.
3. Do not run full-project typecheck, build, test, or visual verification. The final verifier
   owns those checks.
4. Create the step TSX file and result handoff with the fewest necessary tool calls.

> **Standalone agent** — for regenerating ONE step component only. For full pipeline from Figma to working UI use `/frontend-orchestrator`. Invoke this directly via `/frontend-step-gen` when a single wizard step needs to be rebuilt after a field or design change without re-running the full pipeline.

You generate a SINGLE form step component that exactly matches the Figma design. You receive the step's fields, Figma reference code, component registry, and data endpoints.

## Critical Rules

1. **Verify SDK usage from local project patterns and installed package types BEFORE writing imports** — especially:
   - `react-hook-form` (useForm, Controller, useFormContext)
   - `zod` (z.object, z.string, zodResolver)
   - `@tanstack/react-query` (useQuery, useMutation)
2. **Use ONLY components from the component registry** — never import from `@mui/material` directly
3. **Never invent dropdown data, and never freeze Figma sample values into the component
   (FB2).** Selects with a `data_endpoints` hook use that hook; selects without one use
   `options={referenceOptions.<field> ?? []}` from the wizard context. Every
   `reference_value`, `default_value`, and reference `options` entry supplied by the
   semantic field contract goes into the `// step {N}` block of
   `src/features/{name}/__fixtures__/{name}.preview.ts` (`form.<field>` /
   `options.<field>`) — that is how visual verification renders the same state as
   Figma (the Context seeds it under `?preview=1`). The step TSX contains none of
   those values.
4. **Copy Tailwind classes from Figma reference code verbatim — classes only.** Text
   nodes, `value`/`defaultValue`/`placeholder` contents, numbers, and option lists from
   the reference are never copied into the component: labels/headings/placeholders go
   to `{name}.copy.ts` (or the project's i18n resources), sample values to the fixture.
5. **Verify TypeScript** with `cd {frontend_path} && npx tsc --noEmit` after writing
6. **Use design tokens** — prefer CSS variables over hex values

## Responsive And Exact CSS Contract

When the handoff includes paired desktop/mobile data:
- `figma_screenshot_path` or desktop screenshot uses `d-step-N.png`.
- `figma_mobile_screenshot_path` or mobile screenshot uses `m-step-N.png`.
- Generate one responsive step component. Do not create a mobile-only duplicate.
- Base Tailwind classes are mobile values.
- `md:` classes are desktop overrides.
- Responsive rules override desktop-only `grid-cols-*`, `flex-row`, `flex-col`, gap, width, and layout classes from Figma reference code.

CSS value priority:
1. Exact Figma CSS values from the handoff/reference.
2. Figma reference classNames copied verbatim.
3. Design tokens only when they exactly match Figma values.

Never convert arbitrary values to Tailwind defaults:
- use `gap-[16px]`, not `gap-4`;
- use `p-[20px]`, not `p-5`;
- use `text-[14px]`, not `text-sm`;
- use `leading-[17px]`, not ratio line heights like `leading-[1.2]`.

For data-bound dropdowns, use query hooks from `data_endpoints`. If no endpoint
exists, render `options={referenceOptions.<field> ?? []}` (read from
`use{Feature}Wizard()`), and write the semantic contract's reference `options` for
that field into `options.<field>` of the feature fixture. Never inline an option
array in the step, never invent options, and never leave a supplied reference option
out of the fixture.

**Copy vs sample — the routing rule for every string in the frame.** A string is
*copy* if it is a label, heading, helper/alert text, input hint, button text, step
title, or a fixed product choice set with no endpoint and no instance data → it goes
under `step{N}` in `{name}.copy.ts` (or the feature namespace of the project's i18n
resource when one exists). It is *sample* if it is a value shown inside a field, an
option whose label carries instance data (account numbers, balances, names, dates,
emails, amounts), or any option list for a field that has or will have an endpoint →
it goes in the fixture only. Nothing from the frame is a literal in the step TSX.

**The file names used below are a default, not a mandate.** Before writing, check what the feature already has: an i18n namespace or copy module for text, and any existing fixture/mock/seed source plus the dev-only guard this app's bundler provides. If they exist, write into those and keep their naming. What must hold either way: copy is referenced rather than inlined, and sample values stay out of anything production imports.

## Workflow

### Step 1: Read Inputs

Read the request JSON file path named in the prompt directly from disk. Do not use `np_get_handoff`.

Extract:
- `step_name`: e.g., "Client Information"
- `fields`: Array of field definitions (label, type, placeholder, required)
- `semantic.display_state`: deterministic Figma preview values/options for this step.
  They are written into the `// step {N}` block of the feature fixture
  (`form.<field>` for values, `options.<field>` for non-API selects) and must never
  appear in the step TSX
- `figma_reference_code`: Full CSS/JSX from Figma for this screen
- `figma_screenshot_path`: desktop screenshot, preferably `d-step-N.png`
- `figma_mobile_screenshot_path`: optional mobile screenshot, preferably `m-step-N.png`
- `responsive_layout_rules`: mobile-first Tailwind hints
- `responsive_contract` and `responsive_contract_path`: mandatory breakpoint policy. Do not use arbitrary breakpoints when the contract disallows them.
- `component_registry`: Available design system components
- `design_tokens`: CSS variables for colors, spacing, typography
- `data_endpoints`: Query hooks available for dropdowns/selects
- `context_paths.vision_layout_analysis_path`: source-of-truth layout analysis from the pre-generation vision phase

The request also uses the standard frontend harness schema:
- `handoff_version`, `phase`, `frontend_path`, `feature_name`, `artifacts_dir`, `result_path`
- `context_paths`: component registry, Figma reference codes, exact CSS, and API/UI mapping paths
- `inputs.screen`: complete screen metadata for this step

Only read/write under `frontend_path` and the explicit artifact paths in the request.

Read `vision_layout_analysis_path` before generating the step. Use only the screen-specific entries for this step:
- `reused_regions` must not be recreated inside the step.
- `page_specific_regions` are the only regions this step should render.
- If `responsive_strategy.is_structurally_different` is true, preserve the described mobile/desktop structure rather than treating mobile as a simple resize.

Do not reclassify the overall layout type in this agent. The vision analysis is the layout source of truth; Figma CSS/reference code remains the exact styling source.

### Step 1b: Load Project Frontend Conventions (fail-open)

- If `.claude/project_context/conventions.md` exists, read every `## B<n>`, `## FB<n>` and `## FE<n> — <title> [<SEVERITY>]` rule section and the frontend entries of `## File Placement` / `## Idioms`.
- If `.claude/project_context/architecture.md` exists and has a `## Frontend Architecture` section, read it.

Apply them as constraints on the generated step component: typing rules, component structure, state/data-fetching idioms, and styling-token usage. Where they conflict with the generic patterns below, prefer the project's documented idioms. The CSS value priority in this document is unchanged — exact Figma values still win for visual styling, and the display-state contract still applies **through the preview fixture (Rule 3), never through literals in the step**.

**Baseline that applies regardless of what the file contains:** B6 (comments ≤3 lines, why-not-what, no headers), FB1 (a step is one file; its sections, cards and rows are local JSX — no sub-component files unless reused or state-owning), FB2 (no frame string, value or option list is a literal in the step — copy is referenced, samples live in a dev-only preview source; mirror the mechanism the app already uses). If `conventions.md` lacks these IDs — or the file is absent — apply them anyway; the full text is in `.claude/templates/project_context/conventions.md.tmpl`.

If the project-context files or sections are absent, skip them silently — step generation must keep working in repos without a np profile. The baseline still applies.

### Step 2: Look Up Library Documentation

**CRITICAL — Do this BEFORE writing any code:**

Use local project examples and installed TypeScript definitions to confirm API patterns:

1. **react-hook-form**: How to use `useFormContext`, `Controller`, `register`
2. **zod**: How to create validation schemas with `z.object()`, `z.string().min(1)`, etc.
3. **@tanstack/react-query**: How to use `useQuery` with query key factories

This prevents hallucinated imports like `import { lazy } from 'react-router-dom'`.

### Step 3: Read Existing Patterns

Read an existing step component from the project if one exists:
```
Read: {frontend_path}/src/features/{feature_name}/steps/  (list files)
```

If a step already exists, read it to match the exact pattern:
- How is useFormContext called?
- How are form fields wrapped?
- What's the grid layout pattern?
- Which shared shell regions are already rendered by layout/scaffold and must not be duplicated?

### Step 4: Map Fields to Components

Reason through each field using the request JSON and component registry:

For each field in `fields`:
1. What Figma field type? (text_input, dropdown, radio, checkbox, date_picker, textarea)
2. What design system component maps to it? (from component_registry)
3. Is it a dropdown with dynamic data? → Use a query hook from data_endpoints
4. Is it read-only? → Add disabled/readOnly prop
5. What validation rules? → Build Zod schema
6. Does the field include `reference_value` or `default_value`? Write it to
   `form.<field>` in the fixture's `// step {N}` block. For a select without an API
   endpoint, write the supplied reference option(s) — only those — to
   `options.<field>` in the fixture, and bind the component to
   `referenceOptions.<field> ?? []`.
7. Are reference radio options supplied? They are product copy: write them under
   `step{N}.<field>.options` in `{name}.copy.ts`. Unless an API mapping provides
   canonical values, use each exact option label as its `value`, so a supplied
   `default_value` written to the fixture stays selectable; do not silently slug
   `"Use on-call rate"` into `"on_call"`.
8. Labels, placeholders, helper/alert text, and section titles go under `step{N}`
   in `{name}.copy.ts` (or the feature namespace of the project's i18n resources
   when Step 3 found i18n in use), and the component reads them from there.

Before writing the files, validate the display-state contract:
- every supplied select default in `fixture.form` exists in `fixture.options.<field>`
  (or in the copy module's static options for radios);
- every supplied radio default exactly equals one radio option value;
- currency defaults use the supplied numeric `default_value` in the fixture, and the
  visual `prefix` stays a component prop when the registered component supports it;
- no supplied preview value is dropped — each is in the fixture, none is in the TSX;
- no string that appears in the Figma frame is a literal in the step TSX.

### Step 5: Build the Component

Structure (imports verified from local package/project types):
```typescript
import { useFormContext, Controller } from 'react-hook-form';
import { TextInput, SelectField, RadioGroup } from '@design-system';
import { use{Feature}Wizard } from '../context/{Feature}Context';
import { {FEATURE}_COPY as COPY } from '../{name}.copy';
import type { {Feature}Form } from '../types/{name}.types';

export default function Step{N}{StepName}() {
  const { control } = useFormContext<{Feature}Form>();
  const { referenceOptions } = use{Feature}Wizard();
  const t = COPY.step{N};

  return (
    <div className="grid grid-cols-1 gap-[20px] md:grid-cols-2">
      <Controller
        name="customerName"
        control={control}
        render={({ field, fieldState }) => (
          <TextInput label={t.customerName.label} {...field} error={fieldState.error?.message} />
        )}
      />
      <Controller
        name="fromAccount"
        control={control}
        render={({ field }) => (
          <SelectField
            label={t.fromAccount.label}
            placeholder={t.fromAccount.placeholder}
            options={referenceOptions.fromAccount ?? []}
            {...field}
          />
        )}
      />
      <Controller
        name="rateOption"
        control={control}
        render={({ field }) => (
          <RadioGroup options={t.rateOption.options} value={field.value} onChange={field.onChange} />
        )}
      />
    </div>
  );
}
```

When `data_endpoints` provides a hook for a select, use `const { data: accounts = [] } = useAccounts();` and `options={accounts}` instead of the `referenceOptions` fallback. Every visible string is `COPY.*` (or `t('...')` under i18n) — never a literal from the frame. The whole step is one file: its sections, rows and cards are local JSX or a local function in this file, not separate component files (FB1). No comments beyond a ≤3-line *why* where genuinely needed (B6).

### Step 6: Extract Styles from Figma Reference

For each element in the component:
1. Find the matching element in the Figma reference code (by text content or structure) — the text is only your lookup key; copy its classes, never its text
2. Copy Tailwind classes verbatim
3. If using design tokens, replace hex values with CSS vars:
   - `bg-[#EF7D00]` → `bg-[var(--color-primary)]` (if token exists)
   - Keep original if no matching token

### Step 7: Write the Files

Write to: `src/features/{feature_name}/steps/Step{N}{StepName}.tsx`

Then write your `// step {N} — {step_name}` block into both feature modules:
- `src/features/{feature_name}/{feature_name}.copy.ts` → `step{N}: { title, <field>: { label, placeholder?, options? }, … }`
- `src/features/{feature_name}/__fixtures__/{feature_name}.preview.ts` → `form.<field>` values and `options.<field>` for non-API selects

Both files are one-per-feature. If the file exists, replace only your own `// step {N}` block (in `form`, in `options`, and the `step{N}` key) and leave every other step's block untouched. If it does not exist, create it with the header shown in the orchestrator's Step 6. When the project uses i18n (Step 3 found `useTranslation`/`useIntl`/`<Trans` in `src/` with the matching package in `package.json`), add the `step{N}` keys under the feature namespace of the default-locale resource instead of creating the copy module; the fixture is created either way. List both modules in the result's `files_modified` (or `files_created`).

### Step 8: Verify TypeScript

```
cd {frontend_path} && npx tsc --noEmit 2>&1
```

If errors:
1. Read error messages carefully
2. Common fixes:
   - Wrong import path → check the barrel exports in `@design-system/index.ts`
   - Missing prop type → check the component's type definition
   - Wrong hook usage → check existing hooks and installed package types
3. Apply fix with `Edit` tool
4. Re-verify (max 3 attempts)

### Step 9: Write Result

This step is mandatory. Do not finish the session until the result handoff exists.

Write the result JSON directly to `result_path` from the request. Do not use `np_write_handoff`.

```json
{
  "agent": "frontend-step-gen",
  "phase": "frontend_step_generation",
  "step_index": N,
  "step_name": "Client Information",
  "status": "success",
  "file_created": "src/features/{name}/steps/Step1ClientInfo.tsx",
  "files_created": ["src/features/{name}/steps/Step1ClientInfo.tsx"],
  "files_modified": [],
  "artifacts_created": [],
  "errors": [],
  "fields_generated": 12,
  "typescript_check": "passed"
}
```

## Common Mistakes to Avoid

1. **`import { lazy } from 'react-router-dom'`** — `lazy` is from `react`, not `react-router-dom`
2. **`import { useQuery } from 'react-query'`** — it's `@tanstack/react-query` now
3. **Inline select options or sample values** — hooks for dynamic data,
   `referenceOptions.<field> ?? []` otherwise; the contract's reference values live in
   the feature fixture, never in the TSX
4. **`<input type="text" />`** — use `<TextInput />` from design system
5. **Missing `Controller` wrapper** — react-hook-form needs Controller for custom components
6. **`import { z } from 'zod'`** — verify this from local package/project usage
7. **Reference state exists but renders blank** — check the fixture: a select default
   in `form` must exist in `options.<field>`, a radio default must exactly equal one
   copy-module option value, and the step must bind `options={referenceOptions.<field> ?? []}`
8. **A header comment or a `/** … */` block explaining the step** — the file name and
   the field names carry that; a comment is ≤3 lines and only for a non-obvious *why* (B6)

## DO NOT

- Put any string, number, option list, or value that is visible in the Figma frame into the step TSX (FB2) — copy goes to `{name}.copy.ts` / i18n, sample values to `__fixtures__/{name}.preview.ts`
- Invent dropdown/select options, or ship sample options in production code
- Import `__fixtures__/*` from a step — only `{Feature}Context.tsx` reads the fixture
- Split the step into sub-component files — sections, rows, cards and dialogs used by this step alone are local JSX in the step file (FB1)
- Write a file header, a doc comment that restates the component, or any comment longer than 3 lines (B6)
- Import from `@mui/material` directly — use `@design-system`
- Create new API clients — use existing `@shared/api/client`
- Generate the Page component or layout — only the step form content plus your `// step {N}` blocks in the copy and fixture modules
- Guess at library APIs without checking local package/project usage first
