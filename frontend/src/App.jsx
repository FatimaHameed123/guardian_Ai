import { useState, useEffect } from "react";
import { apiLogin, clearAuth } from "./api";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import HeatmapPage from "./pages/HeatmapPage";
import Analytics from "./pages/Analytics";
import Chatbot from "./pages/Chatbot";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
import Login from "./pages/Login";

const PAGE_TITLES = {
  dashboard: "Dashboard",
  heatmap: "Crime heatmap",
  analytics: "Analytics",
  reports: "Case management",
  chatbot: "AI assistant",
  settings: "Settings",
};

export default function App() {
  const [user, setUser] = useState(null);
  const [page, setPage] = useState("dashboard");
  const [dark, setDark] = useState(() => {
    const saved = localStorage.getItem("guardian-theme");
    return saved ? saved === "dark" : true;
  });

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("guardian-theme", dark ? "dark" : "light");
  }, [dark]);

  if (!user) {
    return <Login onLogin={setUser} apiLogin={apiLogin} />;
  }

  const pages = {
    dashboard: <Dashboard />,
    heatmap: <HeatmapPage dark={dark} />,
    analytics: <Analytics />,
    reports: <Reports user={user} />,
    chatbot: <Chatbot />,
    settings: (
      <Settings
        dark={dark}
        setDark={setDark}
        user={user}
        onLogout={() => {
          clearAuth();
          setUser(null);
        }}
      />
    ),
  };

  return (
    <div className="flex min-h-screen bg-slate-50 dark:bg-surface">
      <Sidebar page={page} setPage={setPage} user={user} />
      <main className="flex-1 flex flex-col min-w-0">
        <header className="shrink-0 px-6 lg:px-8 py-4 border-b border-slate-200 dark:border-border bg-white/80 dark:bg-panel/80 backdrop-blur flex items-center justify-between gap-4">
          <div>
            <h1 className="text-lg font-semibold text-slate-900 dark:text-white tracking-tight">
              {PAGE_TITLES[page] || "Guardian AI"}
            </h1>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              Crime prediction & safety monitoring
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setDark(!dark)}
              className="text-xs px-3 py-1.5 rounded-lg border border-slate-200 dark:border-border text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-white/5"
              aria-label="Toggle theme"
            >
              {dark ? "Light" : "Dark"}
            </button>
            <span className="text-xs px-3 py-1.5 rounded-full bg-slate-100 dark:bg-white/5 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-border">
              {user.role}
            </span>
          </div>
        </header>
        <div className="flex-1 p-6 lg:p-8 overflow-auto">{pages[page]}</div>
      </main>
    </div>
  );
}
