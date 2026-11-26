# Flashcard Practice — Business Context

- Three steps (`StepGuide.jsx`, `HomeScreen.jsx`): 1. Nghe & Hiểu — flip the
  card to see the Vietnamese meaning; 2. Nghe & Lặp lại — play the model audio
  and repeat; 3. Luyện nói — open the speaking sheet to record and be scored.
- A sentence (`apps/web/src/data/questions.js`) has `id`, `status`, `en`, `vi`,
  `ipa`, optional `image`. Front of the card is English (+ IPA, speaker);
  back is Vietnamese with the microphone action.
- Learners move prev/next or jump via the sentence drawer; progress shows
  completed/total sentences.
- Model audio uses the browser's Web Speech synthesis (`en-US`, rate 0.9).
