import { useEffect, useState, useCallback } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  AreaChart,
  Area,
  CartesianGrid,
} from "recharts";
import { apiDashboard, apiHeatmap } from "../api";
const COLORS = ["#3b82f6", "#60a5fa", "#6366f1", "#818cf8", "#8b5cf6", "#a78bfa", "#ec4899", "#f472b6"];
export default function Analytics() {
  const [data, setData] = useState(null);
  const [filters, setFilters] = useState({ area: "", crime_type: "", date_from: "", date_to: "" });
  const [areas, setAreas] = useState([]);
  const [crimeTypes, setCrimeTypes] = useState([]);
  const [loading, setLoading] = useState(false);
  // Fetch dropdown filter options
  useEffect(() => {
    apiHeatmap({ max_points: 1 }).then((res) => {
      if (res.areas) setAreas(res.areas);
      if (res.crime_types) setCrimeTypes(res.crime_types);
    }).catch(() => {});
  }, []);
  const loadData = useCallback(() => {
    setLoading(true);
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v)
    );
    apiDashboard(params)
      .then(setData)
      .finally(() => setLoading(false));
  }, [filters]);
  useEffect(() => {
    loadData();
  }, [loadData]);
  const topAreas = data?.top_areas || [];
  const crimes = (data?.crime_distribution || []).slice(0, 8);
  const trend =
    data?.monthly_trend?.map((t) => ({
      month: String(t.month).slice(-7),
      count: t.count,
    })) || [];
  const modelMetrics = data?.model_metrics || {};
  return (
    <div className="space-y-6">
      {/* Top Filter Bar */}
      <div className="flex flex-wrap items-end gap-3 p-4 rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel shadow-sm">
        <div>
          <label className="text-[10px] uppercase tracking-wide text-slate-400 font-semibold">Area</label>
          <select
            className="block mt-1 px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-border dark:bg-surface text-slate-700 dark:text-slate-200 min-w-[140px] focus:ring-1 focus:ring-accent outline-none"
            value={filters.area}
            onChange={(e) => setFilters({ ...filters, area: e.target.value })}
          >
            <option value="">All areas</option>
            {areas.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wide text-slate-400 font-semibold">Crime Category</label>
          <select
            className="block mt-1 px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-border dark:bg-surface text-slate-700 dark:text-slate-200 min-w-[180px] focus:ring-1 focus:ring-accent outline-none"
            value={filters.crime_type}
            onChange={(e) => setFilters({ ...filters, crime_type: e.target.value })}
          >
            <option value="">All categories</option>
            {crimeTypes.slice(0, 40).map((c) => (
              <option key={c} value={c}>{c.length > 36 ? `${c.slice(0, 36)}…` : c}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wide text-slate-400 font-semibold">From</label>
          <input
            type="date"
            className="block mt-1 px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-border dark:bg-surface text-slate-700 dark:text-slate-200 focus:ring-1 focus:ring-accent outline-none"
            value={filters.date_from}
            onChange={(e) => setFilters({ ...filters, date_from: e.target.value })}
          />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wide text-slate-400 font-semibold">To</label>
          <input
            type="date"
            className="block mt-1 px-3 py-2 text-xs rounded-lg border border-slate-200 dark:border-border dark:bg-surface text-slate-700 dark:text-slate-200 focus:ring-1 focus:ring-accent outline-none"
            value={filters.date_to}
            onChange={(e) => setFilters({ ...filters, date_to: e.target.value })}
          />
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-950 hover:bg-slate-900 dark:bg-accent dark:hover:bg-accent/90 text-white disabled:opacity-50 transition-all shadow-sm"
        >
          {loading ? "Filtering…" : "Filter Analytics"}
        </button>
      </div>
      {loading && (
        <div className="flex items-center justify-center p-12">
          <div className="w-8 h-8 border-4 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      )}
      {!loading && (
        <>
          {/* Prediction Confidence Meter / Model Quality Report */}
          {modelMetrics.f1_score != null && (
            <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-5 shadow-sm">
              <div className="flex flex-wrap justify-between items-center mb-4 gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-slate-800 dark:text-slate-200">AI Model Validation Quality Registry</h3>
                  <p className="text-[10px] text-slate-400 mt-0.5">
                    Model: <b className="text-slate-400 dark:text-slate-300">{modelMetrics.selected_model || "Random Forest"}</b> ({modelMetrics.version || "v1"}) · Checked: {modelMetrics.timestamp}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-slate-500 font-semibold">F1 Confidence Rating:</span>
                  <span className="text-sm font-bold text-accent bg-accent/10 border border-accent/20 px-2.5 py-0.5 rounded">
                    {(modelMetrics.f1_score * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
              
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-surface border border-slate-100 dark:border-border/30 text-center">
                  <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Accuracy</div>
                  <div className="mt-1 text-base font-bold text-slate-800 dark:text-slate-100">{(modelMetrics.accuracy * 100).toFixed(1)}%</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-surface border border-slate-100 dark:border-border/30 text-center">
                  <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Precision</div>
                  <div className="mt-1 text-base font-bold text-slate-800 dark:text-slate-100">{(modelMetrics.precision * 100).toFixed(1)}%</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-surface border border-slate-100 dark:border-border/30 text-center">
                  <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Recall</div>
                  <div className="mt-1 text-base font-bold text-slate-800 dark:text-slate-100">{(modelMetrics.recall * 100).toFixed(1)}%</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-50 dark:bg-surface border border-slate-100 dark:border-border/30 text-center">
                  <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">ROC-AUC</div>
                  <div className="mt-1 text-base font-bold text-slate-800 dark:text-slate-100">{(modelMetrics.auc_roc * 100).toFixed(1)}%</div>
                </div>
                <div className="col-span-2 md:col-span-1 p-3 rounded-lg bg-slate-50 dark:bg-surface border border-slate-100 dark:border-border/30 text-center flex flex-col justify-center">
                  <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wider">Reliability Tier</div>
                  <div className="mt-1 text-xs font-bold text-emerald-500">PRODUCTION READY</div>
                </div>
              </div>
            </div>
          )}
          {/* Historical Crime Trend Chart */}
          <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-5 h-72 shadow-sm flex flex-col">
            <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-4">Crime Trend Timeline</h3>
            <div className="flex-1 min-h-0">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                  <defs>
                    <linearGradient id="glowCount" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#818cf8" stopOpacity={0.4} />
                      <stop offset="95%" stopColor="#818cf8" stopOpacity={0.0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#334155" opacity={0.1} />
                  <XAxis dataKey="month" tick={{ fontSize: 9, fill: "#94a3b8" }} />
                  <YAxis tick={{ fontSize: 9, fill: "#94a3b8" }} />
                  <Tooltip
                    contentStyle={{
                      background: "#161b22",
                      border: "1px solid #30363d",
                      borderRadius: "8px",
                      color: "#fff",
                      fontSize: "11px",
                    }}
                  />
                  <Area type="monotone" dataKey="count" stroke="#818cf8" strokeWidth={2.5} fillOpacity={1} fill="url(#glowCount)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
          {/* Grid: Bar Chart & Pie Chart */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Top Areas Comparison */}
            <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-5 h-80 shadow-sm flex flex-col">
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-4">Hotspot Area Volumes</h3>
              <div className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topAreas} layout="vertical" margin={{ left: 24, right: 10 }}>
                    <XAxis type="number" tick={{ fontSize: 9, fill: "#94a3b8" }} />
                    <YAxis type="category" dataKey="area" tick={{ fontSize: 9, fill: "#94a3b8" }} width={80} />
                    <Tooltip
                      contentStyle={{
                        background: "#161b22",
                        border: "1px solid #30363d",
                        borderRadius: "8px",
                        color: "#fff",
                        fontSize: "11px",
                      }}
                    />
                    <Bar dataKey="count" fill="#4f46e5" radius={[0, 4, 4, 0]} barSize={12} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
            {/* Crime Type Distribution */}
            <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-5 h-80 shadow-sm flex flex-col">
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-4">Crime Type Distribution</h3>
              <div className="flex-1 min-h-0 flex items-center justify-center">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={crimes}
                      dataKey="count"
                      nameKey="crime_type"
                      cx="50%"
                      cy="50%"
                      innerRadius={55}
                      outerRadius={85}
                      paddingAngle={3}
                      label={({ crime_type }) => (crime_type?.length > 14 ? `${crime_type.slice(0, 14)}…` : crime_type)}
                      labelLine={false}
                    >
                      {crimes.map((_, i) => (
                        <Cell key={i} fill={COLORS[i % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{
                        background: "#161b22",
                        border: "1px solid #30363d",
                        borderRadius: "8px",
                        color: "#fff",
                        fontSize: "11px",
                      }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
