export default function Header({ runDate, onRefresh, refreshing }) {
  return (
    <header className="sticky top-0 z-20 bg-slate-900/95 backdrop-blur border-b border-slate-800">
      <div className="px-4 py-3 flex items-center justify-between">
        <div className="flex items-baseline gap-2">
          <h1 className="text-xl font-semibold tracking-tight">JobHunt</h1>
          {runDate && (
            <span className="text-xs text-slate-400">as of {runDate}</span>
          )}
        </div>
        <button
          type="button"
          onClick={onRefresh}
          aria-label="Reload jobs"
          className="p-2 rounded-full text-slate-300 hover:text-white hover:bg-slate-800 disabled:opacity-50"
          disabled={refreshing}
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            className={refreshing ? "animate-spin" : ""}
          >
            <path d="M21 12a9 9 0 1 1-2.64-6.36" />
            <polyline points="21 3 21 9 15 9" />
          </svg>
        </button>
      </div>
    </header>
  );
}
