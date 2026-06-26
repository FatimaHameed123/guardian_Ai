import { useEffect, useState } from "react";
import { FLASK_BASE, apiDbInfo } from "../api";

export default function Settings({ dark, setDark, user, onLogout }) {
  const [db, setDb] = useState(null);

  useEffect(() => {
    if (["Admin", "SHO", "Inspector"].includes(user?.role)) {
      apiDbInfo().then(setDb).catch(() => setDb(null));
    }
  }, [user?.role]);

  return (
    <div className="max-w-lg space-y-4">
      <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-5">
        <h3 className="font-medium mb-4">Appearance</h3>
        <button
          onClick={() => setDark(!dark)}
          className="px-4 py-2 rounded-lg border border-slate-200 dark:border-border text-sm"
        >
          {dark ? "Switch to light mode" : "Switch to dark mode"}
        </button>
      </div>
      <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-5">
        <h3 className="font-medium mb-2">API</h3>
        <p className="text-xs text-slate-500 break-all">{FLASK_BASE}</p>
      </div>
      {db?.status === "ok" && (
        <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-5">
          <h3 className="font-medium mb-2">SQLite database</h3>
          <p className="text-xs text-slate-500 break-all">{db.database_file}</p>
          <ul className="mt-2 text-xs text-slate-600 dark:text-slate-400 space-y-1">
            {Object.entries(db.counts || {}).map(([t, n]) => (
              <li key={t}>{t}: {n} rows</li>
            ))}
          </ul>
        </div>
      )}
      <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-5">
        <p className="text-sm">Signed in as <b>{user.username}</b> ({user.role})</p>
        <button onClick={onLogout} className="mt-4 px-4 py-2 text-sm rounded-lg bg-red-500/10 text-red-600 border border-red-500/20">
          Sign out
        </button>
      </div>
    </div>
  );
}
