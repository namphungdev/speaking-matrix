import { useState } from 'react';
import { lessonsData } from './data/lessons';
import { questionsDatabase } from './data/questions';
import { playCardAudio } from './hooks/useSpeech';
import HomeScreen from './components/HomeScreen';
import PracticeScreen from './components/PracticeScreen';
import SpeakingSheet from './components/SpeakingSheet';
import SentenceDrawer from './components/SentenceDrawer';
import Toast from './components/Toast';

export default function App() {
  const [screen, setScreen] = useState('home');
  const [lessonTitle, setLessonTitle] = useState('Bài 01: Giới thiệu bản thân');
  const [currentIndex, setCurrentIndex] = useState(3);
  const [isFlipped, setIsFlipped] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [toast, setToast] = useState({ visible: false, message: '' });

  const completedCount = questionsDatabase.filter((q) => q.status === 'completed').length;

  const showToast = (message) => {
    setToast({ visible: true, message });
    setTimeout(() => setToast({ visible: false, message: '' }), 2200);
  };

  const openLesson = (id, title) => {
    setLessonTitle(title);
    setCurrentIndex(3);
    setIsFlipped(false);
    setScreen('practice');
  };

  const closePractice = () => {
    setScreen('home');
    setSheetOpen(false);
    setDrawerOpen(false);
  };

  const flipCard = () => setIsFlipped((v) => !v);

  const nextQuestion = () => {
    if (currentIndex < questionsDatabase.length - 1) {
      setCurrentIndex((i) => i + 1);
      setIsFlipped(false);
    }
  };

  const prevQuestion = () => {
    if (currentIndex > 0) {
      setCurrentIndex((i) => i - 1);
      setIsFlipped(false);
    }
  };

  const openDrawer = () => setDrawerOpen(true);
  const closeDrawer = () => setDrawerOpen(false);

  const openSheet = () => setSheetOpen(true);
  const closeSheet = () => setSheetOpen(false);

  const playAudio = () => {
    playCardAudio(questionsDatabase[currentIndex].en);
    showToast('🔊 Đang phát âm câu Tiếng Anh...');
  };

  const selectQuestion = (index) => {
    setCurrentIndex(index);
    setIsFlipped(false);
    setDrawerOpen(false);
    showToast(`Đã chuyển sang Câu ${index + 1}`);
  };

  const currentQuestion = questionsDatabase[currentIndex];

  return (
    <div className="min-h-screen flex items-center justify-center p-0 sm:p-4 select-none overflow-x-hidden bg-slate-950">
      <div className="w-full max-w-md h-screen sm:h-[840px] liquid-bg sm:rounded-[40px] shadow-[0_25px_60px_-15px_rgba(0,0,0,0.9)] overflow-hidden flex flex-col relative border-0 sm:border-8 sm:border-slate-800/80">
        <div className="liquid-blob-1" />
        <div className="liquid-blob-2" />
        <div className="liquid-blob-3" />

        <header className="glass-panel px-4 py-3 flex items-center justify-between z-20 flex-shrink-0 border-b border-white/10">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-pink-500 via-purple-500 to-cyan-400 flex items-center justify-center text-white font-bold shadow-[0_0_15px_rgba(236,72,153,0.5)]">
              <i className="fa-solid fa-gem text-xs" />
            </div>
            <div>
              <h1 className="font-bold text-sm font-heading leading-tight tracking-wide bg-gradient-to-r from-white via-slate-200 to-cyan-200 bg-clip-text text-transparent">Speaking Matrix</h1>
              <span className="text-[9px] text-cyan-300 font-semibold tracking-widest uppercase block">Liquid Glass Edition</span>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1.5 bg-black/40 backdrop-blur-md px-2.5 py-1 rounded-full border border-white/10 text-[11px]">
              <span className="text-amber-400">🔥</span>
              <span className="font-bold text-amber-300">5d</span>
              <span className="text-slate-600">|</span>
              <span className="text-pink-400">💎</span>
              <span className="font-bold text-pink-200">120p</span>
            </div>
            <img src="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80" alt="Avatar" className="w-7 h-7 rounded-full object-cover ring-2 ring-cyan-400/60 shadow-md" />
          </div>
        </header>

        <div className="flex-1 flex flex-col overflow-hidden relative z-10">
          {screen === 'home' ? (
            <HomeScreen lessons={lessonsData} onOpenLesson={openLesson} onShowToast={showToast} />
          ) : (
            <PracticeScreen
              lessonTitle={lessonTitle}
              currentIndex={currentIndex}
              question={currentQuestion}
              isFlipped={isFlipped}
              onFlip={flipCard}
              onPrev={prevQuestion}
              onNext={nextQuestion}
              onPlayAudio={playAudio}
              onOpenSpeaking={openSheet}
              onOpenDrawer={openDrawer}
              onClose={closePractice}
            />
          )}
        </div>

        <SentenceDrawer
          open={drawerOpen}
          questions={questionsDatabase}
          currentIndex={currentIndex}
          completedCount={completedCount}
          onSelect={selectQuestion}
          onClose={closeDrawer}
        />

        <SpeakingSheet
          open={sheetOpen}
          targetText={currentQuestion ? currentQuestion.en : ''}
          onClose={closeSheet}
          onPlayModel={playAudio}
          onPlayUser={() => showToast('▶️ Đang phát lại giọng bạn...')}
        />

        <Toast message={toast.message} visible={toast.visible} />
      </div>
    </div>
  );
}
