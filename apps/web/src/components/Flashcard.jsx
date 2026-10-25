export default function Flashcard({ question, isFlipped, onFlip, onPlayAudio, onOpenSpeaking }) {
  if (!question) return null;
  const frontContent = question.image ? (
    <div className="grid grid-cols-2 gap-2.5 items-center w-full">
      <div className="text-left">
        <h3 className="text-xs md:text-sm font-bold text-slate-100 font-heading leading-snug">
          &quot;{question.en}&quot;
        </h3>
      </div>
      <div className="w-full h-28 rounded-2xl overflow-hidden border border-white/10 shadow-inner">
        <img src={question.image} alt="Illustration" className="w-full h-full object-cover" />
      </div>
    </div>
  ) : (
    <div className="text-center px-2">
      <h3 className="text-sm md:text-base font-bold text-slate-100 font-heading leading-relaxed">
        &quot;{question.en}&quot;
      </h3>
    </div>
  );

  return (
    <div className="w-full h-72 perspective-1000 cursor-pointer" onClick={onFlip}>
      <div
        className={`relative w-full h-full transform-style-3d transition-transform duration-500 rounded-3xl ${isFlipped ? 'rotate-y-180' : ''}`}
      >
        {/* Front */}
        <div className="absolute inset-0 w-full h-full glass-panel rounded-3xl p-5 flex flex-col justify-between backface-hidden border border-white/10">
          <div className="flex justify-between items-center text-xs text-cyan-300 font-bold uppercase tracking-wider">
            <span><i className="fa-solid fa-language mr-1" />English</span>
            <span className="text-cyan-300 text-sm"><i className="fa-solid fa-rotate" /></span>
          </div>
          <div className="flex-1 flex items-center justify-center my-2">{frontContent}</div>
          <div className="flex items-end justify-between pt-2 border-t border-white/10">
            <span className="text-[11px] font-mono text-cyan-300 font-medium self-center bg-cyan-950/40 px-2 py-0.5 rounded-md border border-cyan-500/20">{question.ipa}</span>
            <div className="flex items-center space-x-2" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={(e) => { e.stopPropagation(); onPlayAudio && onPlayAudio(); }}
                title="Nghe âm thanh mẫu"
                className="w-10 h-10 rounded-2xl bg-white/10 hover:bg-cyan-500 hover:text-white text-cyan-300 active:scale-95 transition-all shadow-[0_0_15px_rgba(6,182,212,0.2)] flex items-center justify-center text-base border border-white/20"
              >
                <i className="fa-solid fa-volume-high" />
              </button>
            </div>
          </div>
        </div>

        {/* Back */}
        <div className="absolute inset-0 w-full h-full glass-panel bg-slate-900/80 rounded-3xl p-5 flex flex-col justify-between rotate-y-180 backface-hidden border-2 border-pink-500/40 shadow-[0_0_30px_rgba(236,72,153,0.3)]">
          <div className="flex justify-between items-center text-xs text-pink-300 font-bold uppercase tracking-wider">
            <span><i className="fa-solid fa-earth-asia text-amber-400 mr-1" />Tiếng Việt</span>
            <span className="text-amber-300 text-sm"><i className="fa-solid fa-rotate" /></span>
          </div>
          <div className="flex-1 flex items-center justify-center text-center my-2 px-2">
            <h3 className="text-base md:text-lg font-bold font-heading bg-gradient-to-r from-pink-200 via-purple-200 to-cyan-200 bg-clip-text text-transparent leading-relaxed">
              &quot;{question.vi}&quot;
            </h3>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-white/10">
            <p className="text-[10px] text-slate-300 font-medium leading-tight max-w-[190px] text-left">
              💡 Nghe và lặp lại 2 lần trước khi chuyển sang luyện nói
            </p>
            <div className="flex items-center space-x-2 flex-shrink-0" onClick={(e) => e.stopPropagation()}>
              <button
                onClick={(e) => { e.stopPropagation(); onOpenSpeaking && onOpenSpeaking(); }}
                title="Luyện nói"
                className="w-10 h-10 rounded-2xl bg-gradient-to-r from-pink-500 to-rose-600 hover:opacity-90 text-white active:scale-95 transition-all shadow-[0_0_15px_rgba(244,63,94,0.5)] flex items-center justify-center text-base border border-white/20"
              >
                <i className="fa-solid fa-microphone" />
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onPlayAudio && onPlayAudio(); }}
                title="Nghe âm thanh mẫu"
                className="w-10 h-10 rounded-2xl bg-white/10 hover:bg-purple-500 text-purple-300 hover:text-white active:scale-95 transition-all shadow-sm flex items-center justify-center text-base border border-white/20"
              >
                <i className="fa-solid fa-volume-high" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
