# Web Frontend Agent Instructions (`apps/web`)

## 1. Scope & Master Design
- Project: Speaking Matrix Web App (React.js + Vite + Tailwind CSS).
- Living spec: `apps/web/specs/prototype.html`. Consult this file for exact Tailwind classes, colors, 3D card flip effects, spacing, and Liquid Glass styling.
- Design system: Liquid Glass Edition — dark, mobile-first shell with ambient fluid background, glassmorphism surfaces, chromatic borders, gradient accents (pink → purple → cyan).

## 2. Verified Technology & Commands
- Stack: React 18.3.1, Vite 5.4.8, Tailwind CSS 3.4.13, Web Speech API, FontAwesome 6.
- Commands (run in `apps/web`): `npm install`, `npm run dev`, `npm run build`, `npm run preview`.

## 3. UI/UX Design System (Liquid Glass)
- Fonts: `font-sans` = Inter; `font-heading` = Space Grotesk (titles/labels).
- Base body: `bg-slate-950 text-slate-100 font-sans min-h-screen ... select-none overflow-x-hidden`.
- Colors: glass tokens (`base`, `card`, `border`, `highlight`); brand hero `from-pink-500 via-purple-500 to-cyan-400`; CTA `from-cyan-500 via-indigo-600 to-pink-500`; status: emerald (completed), pink (learning), slate (locked), purple (unlearned); recording: rose.
- Legacy tokens `matrix`/`brand`/`Nunito` are deprecated; do not use for new work.
- Icons: FontAwesome 6 (`fa-solid`/`fa-regular`).

## 4. CSS Utilities & Animations (define in `src/index.css`)
- `.no-scrollbar`, `.liquid-bg`, `.liquid-blob-1/2/3`, `.glass-panel`, `.glass-card-interactive`, `.chromatic-border`.
- 3D flip: `.perspective-1000`, `.transform-style-3d`, `.backface-hidden`, `.rotate-y-180`.
- Slide: `.slide-up-enter` (0.38s), `.slide-down-exit` (0.3s).
- Recording: `.recording-pulse`, `.wave-bar`; toast: `.toast-enter`.

## 5. Layout Shell
Mobile-first `max-w-md` shell (`sm:h-[840px]`, `sm:rounded-[40px]`, `sm:border-8 sm:border-slate-800/80`) with 3 ambient blobs (`liquid-blob-1/2/3`) inside. Desktop adds rounded frame + slate border.

## 6. Component Design Rules
- Header: glass panel, gem logo gradient, gradient title text, stats badge, avatar ring cyan.
- Toast: fixed top-centered dark glass + cyan border, `.toast-enter`.
- Sentence Drawer: left 82% glass panel, slide from `-translate-x-full`, progress pill emerald.
- Home Hero Card: glass panel + chromatic border, progress gradient, CTA gradient button with active scale.
- Concept Guide / Lesson Cards: `glass-card-interactive`.
- Practice Top Nav: glass panel, drawer toggle `bars-staggered`, lesson title + `Câu x/y` cyan.
- Step Guide: 3 glass blocks with pink/purple/cyan borders and matching glow shadows.
- Flashcard: front English glass panel (IPA mono cyan, speaker icon), back Vietnamese glass panel (pink border, mic icon strictly on back). Keep 3D flip classes verbatim.
- Speaking Sheet: bottom slide-up glass panel, recording visualizer + wave bars, "Hoàn thành" button.

## 7. Interaction & Motion
- Hover/active via Tailwind transitions (`active:scale-[0.98]`, `transition-all`).
- Slide-up/down for drawer/sheet; recording uses `.recording-pulse` and `.wave-bar`.
- Respect `select-none` on shell.

## 8. UI/UX Component Specs
- 3-Step Fixed Header: always visible, non-interactive visual guide (Nghe & Hiểu / Nghe & Lặp lại / Luyện nói).
- 3D Flip Flashcard: front English, back Vietnamese; speaker icon on both sides, micro icon strictly on back.
- Speaking Modal: slide-up bottom sheet with audio review and "Hoàn thành" button.

## 9. Verification & Feedback Loop (Mandatory)
Before finishing any component or page:
1. Code sanity check: missing imports, syntax errors, unhandled promises.
2. Build verification: `npm run build` inside `apps/web` — zero errors.
3. Responsive UI compliance: mobile-first layout matching `apps/web/specs/prototype.html`, Liquid Glass styles, animations, dark theme.
