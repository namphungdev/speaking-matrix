import { useState } from 'react';

export default function SpeakingSheet({ open, targetText, onClose, onPlayModel, onPlayUser }) {
  const [recording, setRecording] = useState(false);
  const [showResult, setShowResult] = useState(false);

  if (!open) return null;

  const toggleRecording = () => {
    if (!recording) {
      setRecording(true);
      setShowResult(false);
    } else {
      setRecording(false);
      setShowResult(true);
    }
  };

  const handleClose = () => {
    setRecording(false);
    setShowResult(false);
    onClose && onClose();
  };

  return (
    <>
      <div onClick={handleClose} className="fixed inset-0 bg-black/80 backdrop-blur-md z-40 transition-opacity" />
      <div className="fixed bottom-0 left-0 right-0 max-w-md mx-auto glass-panel bg-slate-950/90 text-white z-50 rounded-t-3xl shadow-[0_-15px_40px_rgba(0,0,0,0.9)] border-t border-white/20 flex flex-col overflow-hidden max-h-[85vh] slide-up-enter">
        <div className="p-3.5 px-5 border-b border-white/10 flex items-center justify-between bg-white/5 backdrop-blur-md sticky top-0 z-10">
          <div className="flex items-center space-x-2">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-ping" />
            <h3 className="font-bold text-sm text-slate-100 font-heading">Luyện nói & Chấm điểm</h3>
          </div>
          <button onClick={handleClose} className="w-8 h-8 rounded-full bg-white/10 hover:bg-white/20 text-slate-400 hover:text-white flex items-center justify-center transition">
            <i className="fa-solid fa-xmark text-sm" />
          </button>
        </div>

        <div className="p-5 overflow-y-auto space-y-5 no-scrollbar">
          <div className="glass-panel p-3.5 rounded-2xl border border-white/10 text-center bg-white/5">
            <span className="text-[10px] text-cyan-400 font-bold uppercase tracking-wider block mb-1">Đọc văn bản này:</span>
            <p className="text-sm font-bold text-slate-100 font-heading leading-relaxed">
              &quot;{targetText}&quot;
            </p>
          </div>

          <div className="flex flex-col items-center justify-center py-2 space-y-3">
            <div className="relative">
              <div className={`absolute inset-0 rounded-full bg-rose-500/40 pointer-events-none ${recording ? 'recording-pulse' : 'opacity-0'}`} />
              <button onClick={toggleRecording} className="relative w-20 h-20 rounded-full bg-gradient-to-tr from-rose-500 to-red-600 text-white shadow-xl shadow-rose-600/40 flex items-center justify-center text-3xl hover:scale-105 active:scale-95 transition-all">
                <i className={recording ? 'fa-solid fa-square text-xl' : 'fa-solid fa-microphone'} />
              </button>
            </div>
            <div className={`flex items-center space-x-1.5 h-6 transition-opacity ${recording ? 'opacity-100' : 'opacity-0'}`}>
              <div className="w-1 bg-rose-400 rounded-full wave-bar shadow-[0_0_8px_rgba(244,63,94,0.8)]" />
              <div className="w-1 bg-pink-400 rounded-full wave-bar shadow-[0_0_8px_rgba(236,72,153,0.8)]" />
              <div className="w-1 bg-purple-400 rounded-full wave-bar shadow-[0_0_8px_rgba(168,85,247,0.8)]" />
              <div className="w-1 bg-cyan-400 rounded-full wave-bar shadow-[0_0_8px_rgba(6,182,212,0.8)]" />
              <div className="w-1 bg-emerald-400 rounded-full wave-bar shadow-[0_0_8px_rgba(16,185,129,0.8)]" />
            </div>
            <span className={`text-xs font-semibold ${recording ? 'text-rose-400 animate-pulse font-bold' : 'text-slate-400'}`}>
              {recording ? 'Đang thu âm... Bấm để dừng' : 'Bấm nút Micro để bắt đầu nói'}
            </span>
          </div>

          <div className={`${showResult ? '' : 'hidden'} space-y-3 glass-panel p-4 rounded-2xl border border-white/10 bg-black/40`}>
            <div className="flex justify-between items-center border-b border-white/10 pb-2">
              <span className="text-xs text-slate-400 font-medium">Kết quả nhận diện:</span>
              <span className="text-xs font-bold text-emerald-300 bg-emerald-500/20 px-2.5 py-0.5 rounded-full border border-emerald-500/30">Điểm: 8.8 / 10</span>
            </div>
            <p className="text-sm font-semibold text-slate-200 leading-relaxed">
              &quot;I'd like to <span className="text-emerald-400">order</span> an <span className="text-emerald-400">iced</span> coffee <span className="text-amber-300 underline">with</span> milk...&quot;
            </p>
            <div className="grid grid-cols-2 gap-2 pt-2 border-t border-white/10">
              <button onClick={onPlayModel} className="py-2 px-3 bg-white/10 hover:bg-white/20 rounded-xl text-xs font-semibold text-purple-300 flex items-center justify-center space-x-1.5 border border-white/10">
                <i className="fa-solid fa-volume-high" />
                <span>Nghe bản mẫu</span>
              </button>
              <button onClick={onPlayUser} className="py-2 px-3 bg-white/10 hover:bg-white/20 rounded-xl text-xs font-semibold text-cyan-300 flex items-center justify-center space-x-1.5 border border-white/10">
                <i className="fa-solid fa-play" />
                <span>Nghe lại giọng bạn</span>
              </button>
            </div>
          </div>

          <div className="pt-2">
            <button onClick={() => { setShowResult(false); setRecording(false); onClose && onClose(); }} className="w-full py-3 bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 hover:opacity-90 active:scale-[0.98] transition-all text-white font-bold rounded-2xl shadow-[0_0_20px_rgba(16,185,129,0.4)] flex items-center justify-center space-x-2 text-xs border border-white/20">
              <i className="fa-solid fa-circle-check text-sm" />
              <span>Hoàn thành</span>
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
