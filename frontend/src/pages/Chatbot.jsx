import { useState, useRef, useEffect } from "react";
import { apiChat } from "../api";

function RiskBadge({ meta }) {
  if (!meta) return null;
  const levelColor =
    meta.risk_level === "High"
      ? "text-red-600 bg-red-500/10 border-red-500/20"
      : meta.risk_level === "Medium"
        ? "text-amber-600 bg-amber-500/10 border-amber-500/20"
        : "text-emerald-600 bg-emerald-500/10 border-emerald-500/20";

  return (
    <div className="mt-3 pt-3 border-t border-slate-200 dark:border-border space-y-2">
      <div className="flex flex-wrap gap-2 items-center">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded border ${levelColor}`}>
          {meta.risk_level} risk
        </span>
        <span className="text-xs text-slate-500">Score {meta.risk_score}/100</span>
        <span className="text-xs text-slate-500">Confidence {meta.confidence_score}%</span>
        <span className="text-xs text-slate-500">Trend: {meta.trend_indicator}</span>
      </div>
      <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">{meta.explanation}</p>
    </div>
  );
}

export default function Chatbot() {
  const [msgs, setMsgs] = useState([
    {
      role: "bot",
      text: "Ask about crime risk by area, type, and time. Example: Robbery risk in Hollywood at 11 PM",
      meta: null,
    },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const endRef = useRef();

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [msgs]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const q = input;
    setInput("");
    setMsgs((m) => [...m, { role: "user", text: q, meta: null }]);
    setLoading(true);
    try {
      const res = await apiChat(q);
      setMsgs((m) => [
        ...m,
        {
          role: "bot",
          html: res.reply,
          meta:
            res.risk_score != null
              ? {
                  risk_score: res.risk_score,
                  risk_level: res.risk_level,
                  confidence_score: res.confidence_score,
                  trend_indicator: res.trend_indicator,
                  explanation: res.explanation,
                }
              : null,
        },
      ]);
    } catch {
      setMsgs((m) => [
        ...m,
        { role: "bot", text: "Could not reach the prediction API. Is the backend running?", meta: null },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto flex flex-col h-[calc(100vh-160px)] rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel overflow-hidden shadow-sm">
      <div className="px-4 py-3 border-b border-slate-200 dark:border-border">
        <h2 className="text-sm font-medium text-slate-800 dark:text-slate-200">Safety assistant</h2>
        <p className="text-[11px] text-slate-400">Powered by Random Forest + explainable risk scoring</p>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {msgs.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[88%] rounded-2xl px-4 py-3 text-sm ${
                m.role === "user"
                  ? "bg-slate-900 text-white dark:bg-accent"
                  : "bg-slate-50 dark:bg-surface border border-slate-200 dark:border-border text-slate-800 dark:text-slate-200"
              }`}
            >
              {m.html ? (
                <div className="prose prose-sm dark:prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: m.html }} />
              ) : (
                <p>{m.text}</p>
              )}
              <RiskBadge meta={m.meta} />
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex gap-1 px-2">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse" />
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse [animation-delay:150ms]" />
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse [animation-delay:300ms]" />
          </div>
        )}
        <div ref={endRef} />
      </div>
      <div className="p-4 border-t border-slate-200 dark:border-border flex gap-2 bg-slate-50/50 dark:bg-surface/50">
        <input
          className="flex-1 px-4 py-2.5 rounded-lg border border-slate-200 dark:border-border dark:bg-panel text-sm focus:outline-none focus:ring-2 focus:ring-slate-300 dark:focus:ring-accent/40"
          placeholder="e.g. Robbery risk in Hollywood at 11 PM"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
        />
        <button
          type="button"
          onClick={send}
          disabled={loading}
          className="px-5 py-2.5 rounded-lg bg-slate-900 dark:bg-accent text-white text-sm font-medium disabled:opacity-50"
        >
          Send
        </button>
      </div>
    </div>
  );
}
