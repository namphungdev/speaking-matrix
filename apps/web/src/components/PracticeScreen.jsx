import StepGuide from './StepGuide';
import Flashcard from './Flashcard';

export default function PracticeScreen({
  lessonTitle,
  currentIndex,
  question,
  isFlipped,
  onFlip,
  onPrev,
  onNext,
  onPlayAudio,
  onOpenSpeaking,
  onOpenDrawer,
  onClose,
}) {
  const total = 10;
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden relative z-10">
      {/* Top Nav Bar */}
      <div className="glass-panel px-3.5 py-2.5 border-b border-white/10 flex items-center justify-between z-10 flex-shrink-0">
        <button
          onClick={onOpenDrawer}
          title="Danh sách câu"
          className="w-8 h-8 rounded-xl bg-white/10 text-slate-200 hover:bg-white/20 flex items-center justify-center border border-white/15"
        >
          <i className="fa-solid fa-bars-staggered text-xs" />
        </button>
        <div className="text-center">
          <span className="text-[9px] font-bold text-slate-400 uppercase block truncate max-w-[150px]">{lessonTitle || 'Bài 01'}</span>
          <span className="text-xs font-extrabold text-cyan-300 font-heading">Câu {currentIndex + 1}/{total}</span>
        </div>
        <button
          onClick={onClose}
          className="w-8 h-8 rounded-xl bg-white/10 text-slate-300 flex items-center justify-center hover:bg-white/20 border border-white/15"
        >
          <i className="fa-solid fa-xmark text-xs" />
        </button>
      </div>

      <StepGuide />

      {/* Main flashcard area */}
      <div className="flex-1 overflow-y-auto p-4 flex flex-col justify-between items-center space-y-4 no-scrollbar max-w-md mx-auto w-full">
        <div className="text-center text-[11px] font-medium text-slate-200 bg-white/5 px-3 py-1 rounded-full border border-white/10">
          <i className="fa-solid fa-lightbulb mr-1 text-amber-400" />
          <span>Chạm vào thẻ Flashcard bên dưới để lật mặt trước/sau</span>
        </div>

        <Flashcard
          question={question}
          isFlipped={isFlipped}
          onFlip={onFlip}
          onPlayAudio={onPlayAudio}
          onOpenSpeaking={onOpenSpeaking}
        />

        {/* Navigation Controls */}
        <div className="w-full flex justify-between items-center pt-2">
          <button
            onClick={onPrev}
            disabled={currentIndex <= 0}
            className="text-xs font-bold text-slate-400 hover:text-white flex items-center space-x-1 px-3 py-1.5 rounded-xl hover:bg-white/10 transition disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <i className="fa-solid fa-chevron-left text-[10px]" />
            <span>Câu trước</span>
          </button>
          <button
            onClick={onNext}
            disabled={currentIndex >= total - 1}
            className="text-xs font-bold text-cyan-300 hover:text-cyan-100 flex items-center space-x-1 px-3 py-1.5 rounded-xl hover:bg-cyan-500/20 border border-cyan-500/30 transition shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span>Câu tiếp theo</span>
            <i className="fa-solid fa-chevron-right text-[10px]" />
          </button>
        </div>
      </div>
    </div>
  );
}
