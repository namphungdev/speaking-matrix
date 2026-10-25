function badgeFor(lesson) {
  if (lesson.status === 'completed') {
    return (
      <span className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-[9px] font-bold px-2 py-0.5 rounded-full">
        <i className="fa-solid fa-check mr-1" />Hoàn thành
      </span>
    );
  }
  if (lesson.status === 'learning') {
    return (
      <span className="bg-pink-500/20 text-pink-300 border border-pink-500/30 text-[9px] font-bold px-2 py-0.5 rounded-full">
        Đang học ({lesson.completed}/{lesson.total})
      </span>
    );
  }
  if (lesson.status === 'locked') {
    return (
      <span className="bg-white/5 text-slate-400 text-[9px] font-bold px-2 py-0.5 rounded-full">
        <i className="fa-solid fa-lock mr-1" />Khóa
      </span>
    );
  }
  return <span className="bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[9px] font-bold px-2 py-0.5 rounded-full">Chưa học</span>;
}

export default function HomeScreen({ lessons = [], onOpenLesson, onShowToast }) {
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden relative z-10">
      <div className="flex-1 overflow-y-auto p-4 space-y-4 no-scrollbar">
        <div className="glass-panel rounded-3xl p-4 text-white shadow-2xl relative overflow-hidden flex flex-col justify-between chromatic-border">
          <div className="relative z-10">
            <div className="flex justify-between items-start mb-2">
              <span className="bg-gradient-to-r from-pink-500/30 to-purple-500/30 border border-pink-400/40 text-pink-200 text-[9px] uppercase tracking-wider font-bold px-2.5 py-0.5 rounded-full backdrop-blur-md">Đang luyện</span>
              <span className="text-[10px] text-slate-300 bg-black/40 border border-white/10 px-2 py-0.5 rounded-md"><i className="fa-regular fa-clock mr-1 text-cyan-400" />2 phút</span>
            </div>
            <h3 className="font-bold text-lg mb-1 font-heading bg-gradient-to-r from-white via-slate-100 to-purple-200 bg-clip-text text-transparent">Bài 01: Giới thiệu bản thân</h3>
            <p className="text-xs text-slate-300 mb-4 leading-relaxed">Luyện phản xạ 10 câu bằng phương pháp Liquid Flashcard 3 bước đơn giản.</p>
          </div>
          <div className="space-y-3 relative z-10">
            <div className="space-y-1">
              <div className="flex justify-between text-[11px] font-semibold">
                <span className="text-slate-300">Tiến độ</span>
                <span className="text-cyan-300 font-bold">30% (3/10 câu)</span>
              </div>
              <div className="w-full h-2 bg-black/50 rounded-full overflow-hidden p-0.5 border border-white/10">
                <div className="w-[30%] h-full bg-gradient-to-r from-pink-500 via-purple-500 to-cyan-400 rounded-full shadow-[0_0_10px_rgba(236,72,153,0.8)]" />
              </div>
            </div>
            <button onClick={() => onOpenLesson && onOpenLesson(1, 'Bài 01: Giới thiệu bản thân')} className="w-full bg-gradient-to-r from-cyan-500 via-indigo-600 to-pink-500 hover:opacity-95 active:scale-[0.98] transition-all text-white font-bold py-2.5 rounded-2xl shadow-[0_0_20px_rgba(6,182,212,0.4)] flex items-center justify-center space-x-2 text-xs border border-white/20">
              <span>Bắt đầu lật thẻ học ngay</span>
              <i className="fa-solid fa-arrow-right text-[10px]" />
            </button>
          </div>
        </div>
        <div className="glass-card-interactive p-3.5 rounded-2xl border border-cyan-500/20 text-xs text-slate-200 space-y-1.5">
          <div className="flex items-center space-x-2 text-cyan-300 font-bold font-heading">
            <i className="fa-solid fa-wand-magic-sparkles" />
            <span>Quy trình 3 bước thu gọn:</span>
          </div>
          <p className="text-[11px] text-slate-300 leading-relaxed">
            1. <b className="text-pink-300">Nghe & Hiểu:</b> Chạm Flashcard để lật xem nghĩa Tiếng Việt.<br />
            2. <b className="text-purple-300">Nghe & Lặp lại:</b> Bấm Loa phát âm & Micro nhẩm theo.<br />
            3. <b className="text-cyan-300">Luyện nói:</b> Bấm Micro mở bảng chấm điểm & thu âm.
          </p>
        </div>
        <div className="flex justify-between items-center pt-1">
          <h2 className="font-bold text-slate-100 text-sm font-heading tracking-wide">Danh sách bài học</h2>
          <span className="text-[11px] text-cyan-400 font-semibold">Tất cả (4)</span>
        </div>
        <div className="space-y-2.5 pb-4">
          {lessons.map((lesson) => {
            const borderClass = lesson.status === 'learning' ? 'border-cyan-500/40 shadow-[0_0_20px_rgba(6,182,212,0.15)]' : 'border-white/10';
            const clickable = lesson.status !== 'locked';
            return (
              <div
                key={lesson.id}
                onClick={() => {
                  if (!clickable) {
                    onShowToast && onShowToast('Bài học này chưa mở!');
                    return;
                  }
                  onOpenLesson && onOpenLesson(lesson.id, lesson.title);
                }}
                className={`glass-card-interactive rounded-2xl p-3 border ${borderClass} flex items-center justify-between cursor-pointer active:scale-[0.99]`}
              >
                <div className="flex items-center space-x-3 truncate">
                  <div className={`w-10 h-10 rounded-2xl bg-gradient-to-tr ${lesson.color} text-white flex items-center justify-center text-base shadow-[0_0_15px_rgba(236,72,153,0.3)] flex-shrink-0 border border-white/20`}>
                    <i className={`fa-solid ${lesson.icon}`} />
                  </div>
                  <div className="truncate">
                    <h4 className="font-bold text-slate-100 text-xs font-heading truncate">{lesson.title}</h4>
                    <div className="mt-1 flex items-center space-x-1.5">
                      {badgeFor(lesson)}
                      <span className="text-[10px] text-slate-400">{lesson.total} câu</span>
                    </div>
                  </div>
                </div>
                <div className="text-slate-400 pl-2">
                  <i className="fa-solid fa-chevron-right text-xs" />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

