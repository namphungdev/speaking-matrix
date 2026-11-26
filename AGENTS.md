# Speaking Matrix — Repository-Wide Agent Instructions (Monorepo)

## 1. Project Overview
Speaking Matrix is a monorepo with two components:
- Frontend web app: React.js + Vite + Tailwind CSS (`apps/web`).
- Backend API: .NET 10 ASP.NET Core Web API (`services/api`).

## 2. Repository Map
- `apps/web/` — Web frontend root (`package.json`, `src/`, `specs/prototype.html`).
- `apps/web/src/` — Placeholder; source lives here once implemented.
- `apps/web/specs/prototype.html` — Living design spec (HTML/Tailwind/JS).
- `services/api/` — Backend solution `SpeakingMatrix.slnx` with 3 projects: `SpeakingMatrix.Api`, `SpeakingMatrix.Domain`, `SpeakingMatrix.Application`, `SpeakingMatrix.Infrastructure`.
- `docs/superpowers/plans/` — Implementation plans (e.g. `2026-10-23-flashcard-3d.md`).
- `.claude/skills/` and `.cline/skills/` — Agent skill definitions.

## 3. Verified Technology Stack
- Frontend: React 18.3.1, React DOM 18.3.1, Vite 5.4.8, Tailwind CSS 3.4.13, PostCSS, Autoprefixer, Web Speech API, FontAwesome 6.
- Backend: .NET 10 (`net10.0`), ASP.NET Core Web API, Swashbuckle.AspNetCore 10.3.1, Microsoft.AspNetCore.OpenApi 10.0.13.
- Package managers: npm (frontend), .NET CLI / NuGet (backend).

## 4. Verified Development Commands
Frontend (`apps/web`): `npm install`, `npm run dev`, `npm run build`, `npm run preview`.
Backend (`services/api/SpeakingMatrix`): `dotnet build`, `dotnet run`.

## 5. Repository-Wide Architecture & Dependency Boundaries
- Frontend and backend are independent apps. Never cross-import files directly between them without a shared package.
- Frontend is a Vite + React SPA with conditional screen rendering (no router in the current plan).
- Backend is a layered .NET solution: Api (controllers, Program.cs, Swagger), Domain, Application.

## 6. Cross-Cutting Conventions
- Do not commit secrets, API keys, or environment variables.
- Keep responses focused; avoid generating unrequested boilerplate code.
- Respect architectural boundaries and modular code structure.

## 7. Security & Data Boundaries
- No secrets or credentials in the repository.
- Backend uses `UseHttpsRedirection()` and `UseAuthorization()`; API contract with frontend is not yet defined.

## 8. Testing & Verification Expectations
- Frontend: `npm run build` inside `apps/web` must pass with 0 errors before reporting completion.
- Backend: `dotnet build` inside `services/api/SpeakingMatrix` must pass with 0 errors before reporting completion.
- Do not claim verification unless the command was actually run successfully.

## 9. File & Change Constraints
- Modify only the files explicitly requested; do not touch unrelated files.
- Do not overwrite AGENTS.md wholesale without reviewing existing content first.

## 10. Documentation References
- Living spec: `apps/web/specs/prototype.html`.
- Existing plan: `docs/superpowers/plans/2026-10-23-flashcard-3d.md`.

## 11. Completion-Report Expectations
Report what was changed, which verification commands ran and their actual results, and any unresolved assumptions. Never claim full verification from static inspection alone.
