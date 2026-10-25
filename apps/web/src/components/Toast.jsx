export default function Toast({ message, visible }) {
  return (
    <div
      className={`fixed top-14 left-1/2 transform -translate-x-1/2 bg-slate-900/90 text-white px-4 py-2 rounded-full shadow-[0_10px_30px_rgba(0,0,0,0.8)] z-50 flex items-center space-x-2 text-xs font-medium border border-cyan-500/30 backdrop-blur-xl ${visible ? 'toast-enter' : 'hidden'}`}
    >
      <span>✨</span>
      <span>{message}</span>
    </div>
  );
}
