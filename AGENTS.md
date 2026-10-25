# Repository-Wide Agent Instructions (Monorepo)

## 1. Harness Engineering Philosophy
- This repository operates under strict **Harness Engineering** standards. 
- AI agents must respect architectural boundaries, modular code structure, and perform mandatory self-verification feedback loops before reporting task completion.

## 2. Tech Stack Overview
- **Frontend Web (`apps/web`):** React.js, Vite, Tailwind CSS, FontAwesome 6, Web Speech API.
- **Admin Panel (`apps/admin`):** Reserved for future implementation (directory not yet created).
- **Backend API (`services/api`):** Reserved for future implementation (directory not yet created).

## 3. Monorepo Directory Boundaries (actual layout)
- `.cline/skills/`: Agent skill definitions (e.g. `executing-plans`, `writing-plans`).
- `apps/web/`: Web app root. Contains `AGENTS.md`, `package.json` (currently empty), `specs/`, and `src/`.
- `apps/web/src/`: Present in repository, currently empty. Placeholder directory for source code.
- `apps/web/specs/`: Location for design prototypes, HTML canvases, and Figma exports (Living Specs). Currently contains `prototype.html`.
- `apps/admin/`: **Not yet created** (reserved for future implementation).
- `services/api/`: **Not yet created** (reserved for future implementation).
- Never cross-import files directly between independent apps without a shared package.

## 4. Global Safety & Rules
- Do not commit secrets, API keys, or environment variables.
- Keep responses focused, efficient, and avoid generating unrequested boilerplate code.