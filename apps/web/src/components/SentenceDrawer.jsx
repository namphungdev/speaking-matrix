export default function SentenceDrawer({ open, questions, currentIndex, completedCount, onSelect, onClose }) {
  if (!open) return null;
  return (
    <>
      <div onClick={onClose} className="fixed inset-0 bg-black/70 backdrop-blur-md z-40 transition-opacity duration-300" />
      <div className="fixed top-0 bottom-0 left-0 w-[82%] glass-panel z-50 shadow-2xl flex flex-col bg-slate-950/90 backdrop-blur-2xl border-r border-white/15">
        <div className="p-4 border-b border-white/10 flex justify-between items-center bg-white/5">
          <div>
            <span className="text-[9px] text-cyan-400 uppercase tracking-wider font-bold block">Danh sách câu hỏi</span>
            <h3 className="font-bold text-xs text-slate-100 truncate max-w-[200px] font-heading">Bài 01: Giới thiệu bản thân</h3>
          </div>
          <button onClick={onClose} className="w-7 h-7 rounded-full bg-white/10 flex items-center justify-center text-slate-300 hover:bg-white/20 transition">
            <i className="fa-solid fa-xmark text-xs" />
          </button>
        </div>
        <div className="bg-black/30 p-2.5 px-4 border-b border-white/5 flex justify-between items-center text-xs font-semibold">
          <span className="text-slate-400">Tiến độ bài:</span>
          <span className="text-emerald-300 font-bold bg-emerald-500/20 px-2.5 py-0.5 rounded-full text-[11px] border border-emerald-500/30">
            {completedCount}/{questions.length} đã học
          </span>
        </div>
        <div className="flex-1 overflow-y-auto p-3 space-y-2 no-scrollbar">
          {questions.map((q, index) => {
            const isActive = index === currentIndex;
            let badgeClass = '';
            let statusIcon = '';
            if (q.status === 'completed') {
              badgeClass = 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30';
              statusIcon = <i className="fa-solid fa-circle-check text-emerald-400" />;
            } else if (isActive) {
              badgeClass = 'bg-pink-500/10 text-pink-200 border-pink-500/30 ring-1 ring-pink-500/20';
              statusIcon = <i className="fa-solid fa-spinner animate-spin text-pink-400" />;
            } else {
              badgeClass = 'bg-white/5 text-slate-400 border-white/10';
              statusIcon = <i className="fa-regular fa-circle text-slate-500" />;
            }
            return (
              <div
                key={q.id}
                onClick={() => onSelect && onSelect(index)}
                className={`p-2.5 rounded-xl border text-xs font-medium flex items-center justify-between cursor-pointer transition-all ${badgeClass}`}
              >
                <div className="flex items-center space-x-2 truncate mr-2">
                  <span className="font-bold text-slate-200 min-w-[42px]">Câu {index + 1}</span>
                  <span className="truncate font-normal text-slate-300">{q.en}</span>
                </div>
                <div className="text-sm flex-shrink-0">{statusIcon}</div>
              </div>
            );
          })}
        </div>
        <div className="p-3 border-t border-white/10 bg-black/40 text-center">
          <p className="text-[10px] text-slate-400">Bấm câu bất kỳ để lật thẻ luyện tập</p>
        </div>
      </div>
    </>
  );
}
