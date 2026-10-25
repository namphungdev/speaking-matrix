# Web Frontend Agent Instructions (`apps/web`)

## 1. Scope & Master Design
- **Project:** Speaking Matrix Web App (React.js + Vite + Tailwind CSS).
- **Living Spec Path:** `apps/web/specs/prototype.html`. The agent must consult this file for exact Tailwind classes, colors, 3D card flipping effects, spacing, and Liquid Glass styling.
- **Design System:** **Liquid Glass Edition** — dark, mobile-first shell with ambient fluid background, glassmorphism surfaces, chromatic borders, and gradient accents (pink → purple → cyan).

## 2. UI/UX Design System Guidelines (Liquid Glass)

### 2.1 Tailwind Config (must match prototype)
```js
tailwind.config = {
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
        heading: ['Space Grotesk', 'sans-serif'],
      },
      colors: {
        glass: {
          base: 'rgba(255, 255, 255, 0.05)',
          card: 'rgba(255, 255, 255, 0.08)',
          border: 'rgba(255, 255, 255, 0.18)',
          highlight: 'rgba(255, 255, 255, 0.35)',
        }
      }
    }
  }
}
```
- **Fonts:** `font-sans` = Inter; `font-heading` = Space Grotesk (use for titles/labels).
- **Legacy tokens** `matrix`/`brand`/`Nunito` are deprecated; do not use for new work.
- **Base body:** `bg-slate-950 text-slate-100 font-sans min-h-screen ... select-none overflow-x-hidden`.

### 2.2 Color Palette
- Background: `bg-slate-950` (`#060810` shell via `.liquid-bg`).
- Text: `text-slate-100` primary, `text-slate-300/400` secondary, `text-cyan-300/400` accent.
- Accent gradients:
  - Brand hero: `from-pink-500 via-purple-500 to-cyan-400`
  - CTA button: `from-cyan-500 via-indigo-600 to-pink-500`
  - Text gradient: `from-white via-slate-100/200 to-purple-200` + `bg-clip-text text-transparent`
  - VI text: `from-pink-200 via-purple-200 to-cyan-200`
- Status: emerald (completed), pink (learning), slate (locked), purple (unlearned).
- Recording: rose `rose-500/600` with pulse glow.

### 2.3 CSS Utility Classes (define in `src/index.css`)
- `.no-scrollbar`: hide scrollbars (webkit/IE/Firefox).
- `.liquid-bg`: `background: #060810; position: relative; overflow: hidden;`
- `.liquid-blob-1/2/3`: ambient radial gradients with blur and animation:
  - blob1: pink→purple, blur 50px, 12s
  - blob2: cyan→blue, blur 60px, 15s
  - blob3: emerald→indigo, blur 45px, 10s
- `.glass-panel`: `rgba(255,255,255,0.06)` + `backdrop-filter: blur(20px)` + border `rgba(...,0.16)` + layered shadow/inset highlight.
- `.glass-card-interactive`: `rgba(...,0.05)` + blur(16px) + hover lift `translateY(-2px)` + indigo glow.
- `.chromatic-border`: `::before` gradient border (pink→blue→emerald) using mask xor/exclude, inset -1px, radius inherit.
- 3D flip (unchanged): `.perspective-1000`, `.transform-style-3d`, `.backface-hidden`, `.rotate-y-180`.
- Slide: `.slide-up-enter` (0.38s), `.slide-down-exit` (0.3s).
- Recording: `.recording-pulse` (pulse-ring), `.wave-bar` (audio-wave with nth-child delays).
- Toast: `.toast-enter` (slideUpFade).

### 2.4 Animations (keyframes)
- `floatBlob1/2/3`: translate + scale, infinite alternate ease-in-out.
- `slideUp` / `slideDown`: translateY 100% ↔ 0.
- `pulse-ring`: scale + rose box-shadow.
- `audio-wave`: height 6px ↔ 28px.
- `slideUpFade`: opacity + translateY for toast.
### 2.5 Layout Shell
```html
<div class="w-full max-w-md h-screen sm:h-[840px] liquid-bg sm:rounded-[40px]
  shadow-[0_25px_60px_-15px_rgba(0,0,0,0.9)] overflow-hidden flex flex-col relative
  border-0 sm:border-8 sm:border-slate-800/80">
  <div class="liquid-blob-1"></div>
  <div class="liquid-blob-2"></div>
  <div class="liquid-blob-3"></div>
  <!-- header / content / overlays -->
</div>
```
- Always render 3 ambient blobs inside shell.
- Mobile-first, max-w-md; desktop has rounded frame + slate border.

### 2.6 Component Design Rules
- **Header:** `glass-panel px-4 py-3 ... border-b border-white/10`, logo gem gradient, title gradient text, stats badge dark glass, avatar ring cyan.
- **Toast:** fixed top-14 centered, dark glass + cyan border, icon + text, `.toast-enter`.
- **Sentence Drawer:** left, width 82%, `glass-panel ... bg-slate-950/90 backdrop-blur-2xl`, slide from `-translate-x-full`; header cyan label; progress pill emerald; footer hint.
- **Home Hero Card:** `glass-panel rounded-3xl ... chromatic-border`; badge “Đang luyện”; progress bar gradient; CTA gradient button with active scale.
- **Concept Guide:** `glass-card-interactive border-cyan-500/20`.
- **Lesson Cards:** `glass-card-interactive rounded-2xl border ...`; icon gradient square; status badges by state.
- **Practice Top Nav:** glass-panel, drawer toggle `bars-staggered`, lesson title + `Câu x/y` cyan, close button.
- **Step Guide:** 3 glass blocks with colored borders (pink/purple/cyan) + matching glow shadows.
- **Flashcard:** front glass-panel with EN gradient text, IPA mono cyan, volume button; back glass-panel pink border with VI gradient text, hint, mic + volume buttons. Keep 3D flip classes verbatim.
- **Speaking Sheet:** bottom slide-up `glass-panel bg-slate-950/90 rounded-t-3xl max-h-[85vh]`; header rose ping dot; target sentence glass panel; recording visualizer + wave bars; result/actions.
- **Icons:** FontAwesome 6 (`fa-solid`/`fa-regular`), sized consistently with prototype.

### 2.7 Interaction & Motion
- Use Tailwind transitions for hover/active (`active:scale-[0.98]`, `transition-all`).
- Slide-up/down animations for drawer/sheet via `.slide-up-enter`/`.slide-down-exit`.
- Recording uses `.recording-pulse` and `.wave-bar` animations.
- Respect `select-none` on shell.

## 3. UI/UX Component Specifications
- **3-Step Fixed Header:** Always visible at top as non-interactive visual guide (Step 1: Nghe & Hiểu, Step 2: Nghe & Lặp lại, Step 3: Luyện nói).
- **3D Flip Flashcard:** Front (English), Back (Vietnamese). Speaker icon on both sides, Micro icon strictly on back side.
- **Speaking Modal:** Slide-up bottom sheet triggered by micro icon, featuring audio review and prominent **"Hoàn thành"** button.

## 4. Development Commands
- Install: `npm install`
- Dev Server: `npm run dev`
- Production Build: `npm run build`

## 5. Verification & Feedback Loop (Mandatory)
Before finishing any component or page implementation, the agent **MUST** run:
1. **Code Sanity Check:** missing imports, syntax errors, unhandled promises.
2. **Build Verification:** run `npm run build` inside `apps/web` for zero errors.
3. **Responsive UI Compliance:** mobile-first fluid layout matching `apps/web/specs/prototype.html`, including Liquid Glass styles, animations, and dark theme.

