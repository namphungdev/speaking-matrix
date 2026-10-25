# Flashcard 3-Step Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `@executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Speaking Matrix Flashcard 3-step web experience (Home, Practice with 3D flip card, Speaking sheet, Sentence drawer, Toast) matching the living spec.

**Architecture:** A Vite + React single-page app with state lifted to `App.jsx` (screen switching via conditional rendering, no router). UI is split into focused components (HomeScreen, PracticeScreen, Flashcard, SpeakingSheet, SentenceDrawer, Toast) consuming static data modules. Animations use Tailwind utility classes + small CSS keyframes ported from the prototype.

**Tech Stack:** React.js, Vite, Tailwind CSS, Web Speech API (prototype uses FontAwesome 6; AGENTS.md lists Lucide — see Review Focus).

**Living Spec:** `apps/web/specs/prototype.html`

## Global Constraints
- Strictly maintain mobile-first responsive constraints matching `apps/web/specs/prototype.html` (max-w-md shell, rounded cards, spacing).
- Use Tailwind CSS utility classes. Avoid raw inline CSS except for dynamic CSS variables or 3D transform properties.
- All code must pass `npm run build` inside `apps/web` without syntax or compilation errors.

## Review Focus
- Icon library mismatch: prototype uses FontAwesome 6 (`fa-solid ...`), AGENTS.md says Lucide Icons. Decision in this plan: use FontAwesome 6 to match the living spec exactly; align AGENTS.md tech stack in a follow-up edit. If Lucide is preferred instead, swap icon classes during implementation.
- 3D flip card transforms (`perspective`, `transform-style: preserve-3d`, `backface-visibility`) must render correctly on iOS Safari; keep the prototype's CSS classes verbatim.
- Web Speech API (`speechSynthesis`) is not available in all browsers; guard with `'speechSynthesis' in window` and show toast fallback.
- Recording is UI-simulated in the prototype (no MediaRecorder); do not block build on real audio capture. Keep mock toggle behavior.
- Tailwind custom colors/fonts (`matrix`, `brand`, `Inter`, `Nunito`) must be defined in `tailwind.config.js` before use.

## File Structure Mapping
- `apps/web/package.json` — scripts & dependencies
- `apps/web/vite.config.js` — Vite + React plugin
- `apps/web/tailwind.config.js` — theme (colors `matrix`, `brand`, fonts)
- `apps/web/postcss.config.js` — Tailwind/autoprefixer
- `apps/web/index.html` — entry HTML, font/icon CDN links
- `apps/web/src/main.jsx` — React root
- `apps/web/src/index.css` — Tailwind directives + animation keyframes
- `apps/web/src/App.jsx` — app state + screen switching
- `apps/web/src/data/lessons.js` — lessons array
- `apps/web/src/data/questions.js` — questions array (10 items)
- `apps/web/src/hooks/useSpeech.js` — `playCardAudio(en)`
- `apps/web/src/components/StepGuide.jsx` — 3 fixed step blocks
- `apps/web/src/components/HomeScreen.jsx` — hero + lesson list
- `apps/web/src/components/Flashcard.jsx` — 3D flip card
- `apps/web/src/components/PracticeScreen.jsx` — practice layout + nav + footer
- `apps/web/src/components/SpeakingSheet.jsx` — slide-up bottom sheet
- `apps/web/src/components/SentenceDrawer.jsx` — left drawer + backdrop
- `apps/web/src/components/Toast.jsx` — toast helper (render + show function)

---

### Task 1: Project Scaffold (Vite + React + Tailwind)

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/vite.config.js`
- Create: `apps/web/tailwind.config.js`
- Create: `apps/web/postcss.config.js`
- Create: `apps/web/index.html`
- Create: `apps/web/src/main.jsx`
- Create: `apps/web/src/index.css`

**Interfaces:**
- Produces: runnable Vite dev/build, Tailwind theme tokens `colors.matrix.*`, `colors.brand.*`, `fontFamily.sans`, `fontFamily.heading`.

- [ ] **Step 1: Write package.json**
  ```json
  {
    "name": "speaking-matrix-web",
    "private": true,
    "version": "0.0.0",
    "type": "module",
    "scripts": {
      "dev": "vite",
      "build": "vite build",
      "preview": "vite preview"
    },
    "dependencies": {
      "react": "^18.3.1",
      "react-dom": "^18.3.1"
    },
    "devDependencies": {
      "@vitejs/plugin-react": "^4.3.1",
      "autoprefixer": "^10.4.20",
      "postcss": "^8.4.47",
      "tailwindcss": "^3.4.13",
      "vite": "^5.4.8"
    }
  }
  ```

- [ ] **Step 2: Write vite/tailwind/postcss configs and index.html**
  `vite.config.js`: `import { defineConfig } from 'vite'; import react from '@vitejs/plugin-react'; export default defineConfig({ plugins: [react()] });`
  `tailwind.config.js`: content `./index.html`, `./src/**/*.{js,jsx}`; theme extend colors matrix/brand and fonts (Inter/Nunito) exactly as prototype.
  `postcss.config.js`: tailwindcss + autoprefixer.
  `index.html`: include Tailwind via build (no CDN), Google Fonts Inter/Nunito, FontAwesome 6 CDN, root div `#root`, script main.jsx.

- [ ] **Step 3: Write main.jsx + index.css**
  `main.jsx`: ReactDOM.createRoot render `<App />`.
  `index.css`: `@tailwind base; @tailwind components; @tailwind utilities;` plus ported keyframes/utilities: `.no-scrollbar`, `.perspective-1000`, `.transform-style-3d`, `.backface-hidden`, `.rotate-y-180`, `.slide-up-enter`, `.slide-down-exit`, `@keyframes slideUp/slideDown`, `.recording-pulse`, `.wave-bar`, `.toast-enter`.

- [ ] **Step 4: Verification Step**
  Run: `cd apps/web && npm install && npm run build`
  Expected: install succeeds and build outputs dist with 0 errors.
---

### Task 2: Static Data Modules

**Files:**
- Create: `apps/web/src/data/lessons.js`
- Create: `apps/web/src/data/questions.js`

**Interfaces:**
- Produces: `export const lessonsData = [...]` (id, title, subtitle, total, completed, status, icon, color)
- Produces: `export const questionsDatabase = [...]` (id, en, vi, ipa, image?, status)

- [ ] **Step 1: Port lessonsData** exactly from prototype (4 lessons).
- [ ] **Step 2: Port questionsDatabase** exactly from prototype (10 questions, including image URLs where present).
- [ ] **Step 3: Verification Step**
  Run: `cd apps/web && npm run build`
  Expected: 0 errors.

---

### Task 3: Speech Hook

**Files:**
- Create: `apps/web/src/hooks/useSpeech.js`

**Interfaces:**
- Consumes: none
- Produces: `export function playCardAudio(text)` (cancels ongoing, speaks en-US rate 0.9, toast fallback handled by caller) and `export function useSpeech()` returning `{ play }`.

- [ ] **Step 1: Implement guard + speak** using `window.speechSynthesis` if available.
- [ ] **Step 2: Verification Step**
  Run: `cd apps/web && npm run build`
  Expected: 0 errors.

---

### Task 4: Toast Component

**Files:**
- Create: `apps/web/src/components/Toast.jsx`

**Interfaces:**
- Consumes: `message: string`, `visible: boolean`
- Produces: `<Toast message visible />`

- [ ] **Step 1: Scaffold JSX** matching prototype toast markup (fixed bottom, slide-up fade).
- [ ] **Step 2: Implement visibility toggle** with `hidden` class and `toast-enter`.
- [ ] **Step 3: Verification Step**
  Run: `cd apps/web && npm run build`
  Expected: 0 errors.

---

### Task 5: StepGuide Component

**Files:**
- Create: `apps/web/src/components/StepGuide.jsx`

**Interfaces:**
- Consumes: none (static 3 steps)
- Produces: `<StepGuide />`

- [ ] **Step 1: Port 3 step blocks** with exact Tailwind classes from prototype (emerald active styling).
- [ ] **Step 2: Verification Step**
  Run: `cd apps/web && npm run build`
  Expected: 0 errors.

---

### Task 6: HomeScreen Component

**Files:**
- Create: `apps/web/src/components/HomeScreen.jsx`

**Interfaces:**
- Consumes: `lessons`, `onOpenLesson(id, title)` 
- Produces: `<HomeScreen lessons onOpenLesson />`

- [ ] **Step 1: Scaffold** hero card + concept quick guide + lesson list container.
- [ ] **Step 2: Implement lesson list rendering** (status badges: learning/open/completed) and progress.
- [ ] **Step 3: Wire onOpenLesson** to hero button and lesson cards.
- [ ] **Step 4: Verification Step**
  Run: `cd apps/web && npm run build`
  Expected: 0 errors.

---

### Task 7: Flashcard Component (3D Flip)

**Files:**
- Create: `apps/web/src/components/Flashcard.jsx`

**Interfaces:**
- Consumes: `question: {en, vi, ipa, image?}`, `isFlipped: boolean`, `onFlip: () => void`, `onPlayAudio: () => void`, `onOpenSpeaking: () => void`
- Produces: `<Flashcard ... />`

- [ ] **Step 1: Scaffold card container** with `.perspective-1000` and inner `.transform-style-3d`.
- [ ] **Step 2: Front side** — conditional layout: dual-column if image else centered text; IPA hint; speaker button; (micro icon only on back per spec).
- [ ] **Step 3: Back side** — Vietnamese text, speaker button, micro button opening speaking sheet.
- [ ] **Step 4: Apply `.rotate-y-180` based on isFlipped; backface-hidden both sides.**
---

### Task 8: PracticeScreen Component

**Files:**
- Create: `apps/web/src/components/PracticeScreen.jsx`

**Interfaces:**
- Consumes: `lessonTitle`, `currentIndex`, `question`, `isFlipped`, `onFlip`, `onPrev`, `onNext`, `onPlayAudio`, `onOpenSpeaking`, `onOpenDrawer`, `onClose`
- Produces: `<PracticeScreen ... />`

- [ ] **Step 1: Scaffold** top nav bar + StepGuide + card area + footer nav.
- [ ] **Step 2: Wire Flashcard** and navigation buttons (prev/next, disabled bounds).
- [ ] **Step 3: Show progress text** `Câu {n}/10`.
- [ ] **Step 4: Verification Step**
  Run: `cd apps/web && npm run build`
  Expected: 0 errors.

---

### Task 9: SpeakingSheet Component

**Files:**
- Create: `apps/web/src/components/SpeakingSheet.jsx`

**Interfaces:**
- Consumes: `open: boolean`, `targetText: string`, `onClose: () => void`, `onPlayModel: () => void`, `onPlayUser: () => void`
- Produces: `<SpeakingSheet ... />` with internal recording state (mock).

- [ ] **Step 1: Scaffold** backdrop + sheet container with slide-up animation classes.
- [ ] **Step 2: Implement recording toggle** (pulse ring, icon swap square/mic, wave bars, status text, result box reveal).
- [ ] **Step 3: Implement action buttons** model/user playback + "Hoàn thành" submit.
- [ ] **Step 4: Verification Step**
  Run: `cd apps/web && npm run build`
  Expected: 0 errors.

---

### Task 10: SentenceDrawer Component

**Files:**
- Create: `apps/web/src/components/SentenceDrawer.jsx`

**Interfaces:**
- Consumes: `open: boolean`, `questions`, `currentIndex`, `completedCount`, `onSelect(index)`, `onClose`
- Produces: `<SentenceDrawer ... />`

- [ ] **Step 1: Scaffold** backdrop + drawer panel with header/progress/list/footer.
- [ ] **Step 2: Render question items** with status styling (completed/active/pending) and click select.
- [ ] **Step 3: Verification Step**
  Run: `cd apps/web && npm run build`
  Expected: 0 errors.

---

### Task 11: App.jsx Integration

**Files:**
- Create: `apps/web/src/App.jsx`

**Interfaces:**
- Consumes: data modules, components
- Produces: default export `App`

- [ ] **Step 1: Lift state** (screen, lessonTitle, currentIndex, isFlipped, drawerOpen, sheetOpen, toast).
- [ ] **Step 2: Implement handlers** openLesson, closePractice, flipCard, next/prev, open/close drawer & sheet, showToast with timeout.
- [ ] **Step 3: Compose screens** conditionally render HomeScreen/PracticeScreen; render drawer, sheet, toast overlays.
- [ ] **Step 4: Verification Step**
  Run: `cd apps/web && npm run build`
  Expected: 0 errors.

---

### Task 12: Final Verification & Smoke Test

**Files:**
- Modify: (none expected)

**Interfaces:**
- Consumes: all prior
- Produces: validated build

- [ ] **Step 1: Build**
  Run: `cd apps/web && npm run build`
  Expected: 0 errors.
- [ ] **Step 2: Dev smoke test**
  Run: `cd apps/web && npm run dev` then open browser; verify Home → open lesson → flip card → open speaking sheet → drawer → toast.
  Expected: no console errors; animations work.
- [ ] **Step 3: Commit (optional)**
  ```bash
  git add apps/web
  git commit -m "feat(web): implement flashcard 3-step experience"
  ```

---
- [ ] **Step 5: Verification Step**
  Run: `cd apps/web && npm run build`
  Expected: 0 errors.