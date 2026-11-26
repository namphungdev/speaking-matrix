# Lessons — Business Context

- A lesson has `id`, `title`, `subtitle`, `total` sentences, `completed` count,
  `status`, `icon`, `color` (`apps/web/src/data/lessons.js`).
- Status values: `completed`, `learning`, `open` (not started), `locked`.
  Locked lessons cannot be opened (`HomeScreen.jsx` shows a toast instead).
- Lesson data is static in the web app; no backend model or endpoint exists yet.
