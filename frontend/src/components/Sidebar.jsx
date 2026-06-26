const NAV = [
  { id: "dashboard", label: "Dashboard" },
  { id: "heatmap", label: "Heatmap" },
  { id: "analytics", label: "Analytics" },
  { id: "reports", label: "Cases" },
  { id: "chatbot", label: "Chatbot" },
  { id: "settings", label: "Settings" },
];

export default function Sidebar({ page, setPage, user }) {
  return (
    <aside className="w-60 shrink-0 border-r border-slate-200 dark:border-border bg-white dark:bg-panel flex flex-col">
      <div className="p-6 border-b border-slate-200 dark:border-border">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-slate-900 dark:bg-accent flex items-center justify-center text-white text-xs font-bold">
            G
          </div>
          <div>
            <div className="text-sm font-semibold text-slate-900 dark:text-white">Guardian AI</div>
            <div className="text-[10px] text-slate-400">Safety monitoring</div>
          </div>
        </div>
      </div>
      <nav className="flex-1 p-3 space-y-0.5">
        {NAV.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setPage(item.id)}
            className={`w-full text-left px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
              page === item.id
                ? "bg-slate-900 text-white dark:bg-accent"
                : "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-white/5"
            }`}
          >
            {item.label}
          </button>
        ))}
      </nav>
      <div className="p-4 border-t border-slate-200 dark:border-border">
        <p className="text-xs font-medium text-slate-700 dark:text-slate-300 truncate">{user.username}</p>
        <p className="text-[10px] text-slate-400 mt-0.5">RF + risk regression</p>
      </div>
    </aside>
  );
}
