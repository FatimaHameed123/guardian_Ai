import { useState } from "react";

export default function Login({ onLogin, apiLogin }) {
  const [u, setU] = useState("");
  const [p, setP] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    setErr("");
    const res = await apiLogin(u, p);
    setLoading(false);
    if (res.status === "success") {
      onLogin({ username: res.username || u, role: res.role, area: res.area });
    } else {
      setErr(res.message || "Login failed");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100 dark:bg-surface p-4">
      <div className="w-full max-w-md rounded-2xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-8 shadow-xl">
        <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Guardian AI</h1>
        <p className="text-sm text-slate-500 mt-1 mb-6">Sign in to access the safety dashboard</p>
        <input
          className="w-full mb-3 px-4 py-2.5 rounded-lg border border-slate-200 dark:border-border bg-slate-50 dark:bg-surface text-sm"
          placeholder="Username"
          value={u}
          onChange={(e) => setU(e.target.value)}
        />
        <input
          type="password"
          className="w-full mb-4 px-4 py-2.5 rounded-lg border border-slate-200 dark:border-border bg-slate-50 dark:bg-surface text-sm"
          placeholder="Password"
          value={p}
          onChange={(e) => setP(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submit()}
        />
        {err && <p className="text-red-500 text-sm mb-3">{err}</p>}
        <button
          onClick={submit}
          disabled={loading}
          className="w-full py-2.5 rounded-lg bg-slate-900 dark:bg-accent text-white text-sm font-medium hover:opacity-90 disabled:opacity-50"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
        <p className="text-[11px] text-slate-400 mt-4 text-center">Demo: admin_alishba / admin123</p>
      </div>
    </div>
  );
}
