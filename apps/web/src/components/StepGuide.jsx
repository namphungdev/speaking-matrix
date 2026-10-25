export default function StepGuide() {
  return (
    <div className="p-3 bg-black/20 border-b border-white/10 flex-shrink-0 z-10 backdrop-blur-md">
      <div className="grid grid-cols-3 gap-1.5 text-center">
        <div className="glass-panel border border-pink-500/40 p-2 rounded-2xl flex flex-col items-center justify-center transition-all shadow-[0_0_15px_rgba(236,72,153,0.15)]">
          <span className="text-[9px] font-black text-pink-400 uppercase tracking-tight block">Bước 1</span>
          <span className="text-[11px] font-bold text-white font-heading leading-tight truncate w-full">Nghe & Hiểu</span>
        </div>
        <div className="glass-panel border border-purple-500/40 p-2 rounded-2xl flex flex-col items-center justify-center transition-all shadow-[0_0_15px_rgba(168,85,247,0.15)]">
          <span className="text-[9px] font-black text-purple-400 uppercase tracking-tight block">Bước 2</span>
          <span className="text-[11px] font-bold text-white font-heading leading-tight truncate w-full">Nghe & Lặp lại</span>
        </div>
        <div className="glass-panel border border-cyan-500/40 p-2 rounded-2xl flex flex-col items-center justify-center transition-all shadow-[0_0_15px_rgba(6,182,212,0.15)]">
          <span className="text-[9px] font-black text-cyan-400 uppercase tracking-tight block">Bước 3</span>
          <span className="text-[11px] font-bold text-white font-heading leading-tight truncate w-full">Luyện nói</span>
        </div>
      </div>
    </div>
  );
}
