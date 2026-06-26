import { useEffect, useState, useCallback } from "react";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import StatCard from "../components/StatCard";
import { apiDashboard, apiHeatmap } from "../api";
export default function Dashboard() {
  const [data, setData] = useState(null);
  const [filters, setFilters] = useState({ area: "", crime_type: "", date_from: "", date_to: "" });
  const [areas, setAreas] = useState([]);
  const [crimeTypes, setCrimeTypes] = useState([]);
  const [loading, setLoading] = useState(false);
  // Fetch filter dropdown options on mount
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
      .then((d) => {
        setData(d);
      })
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [filters]);
  useEffect(() => {
    loadData();
  }, [loadData]);
  const trend = data?.monthly_trend?.map((t) => ({
    month: String(t.month).slice(-7),
    count: t.count,
  })) || [];
  const topAreas = data?.top_areas || [];
  const totalIncidents = data?.total_incidents ?? 0;
  const avgRiskScore = data?.avg_risk_score ?? 0;
  // Determine overall risk level
  const getRiskLabel = (score) => {
    if (score >= 65) return { text: "High Risk", color: "text-red-500", bg: "bg-red-500/10 border-red-500/20", progress: "bg-red-500" };
    if (score >= 35) return { text: "Medium Risk", color: "text-amber-500", bg: "bg-amber-500/10 border-amber-500/20", progress: "bg-amber-500" };
    return { text: "Low Risk", color: "text-emerald-500", bg: "bg-emerald-500/10 border-emerald-500/20", progress: "bg-emerald-500" };
  };
  const riskTier = getRiskLabel(avgRiskScore);
  return (
    <div className="space-y-6">
      {/* Dynamic Filter Section */}
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
          className="px-4 py-2 text-xs font-semibold rounded-lg bg-slate-900 hover:bg-slate-800 dark:bg-accent dark:hover:bg-accent/90 text-white disabled:opacity-50 transition-all shadow-sm"
        >
          {loading ? "Refreshing…" : "Filter Dashboard"}
        </button>
      </div>
      {loading && (
        <div className="flex items-center justify-center p-12">
          <div className="w-8 h-8 border-4 border-accent border-t-transparent rounded-full animate-spin" />
        </div>
      )}
      {!loading && (
        <>
          {/* Main Stat Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <StatCard
              label="Total Incidents"
              value={totalIncidents.toLocaleString()}
              sub={filters.area || filters.crime_type ? "Filtered dataset subset" : "Complete historical volume"}
            />
            <StatCard
              label="Hotspot Regions"
              value={data?.high_risk_areas ?? "—"}
              sub="Top quartile incident density"
            />
            {/* Custom Risk Indicator Card */}
            <div className={`rounded-xl border p-5 shadow-sm bg-white dark:bg-panel ${riskTier.bg} transition-all duration-300`}>
              <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide">Threat Level Index</p>
              <div className="mt-2 flex items-baseline justify-between">
                <span className={`text-2xl font-bold ${riskTier.color}`}>{riskTier.text}</span>
                <span className="text-sm text-slate-400 font-medium">{avgRiskScore}% weight</span>
              </div>
              <div className="w-full bg-slate-200 dark:bg-border h-1.5 rounded-full mt-3 overflow-hidden">
                <div className={`${riskTier.progress} h-1.5 rounded-full transition-all duration-500`} style={{ width: `${avgRiskScore}%` }} />
              </div>
            </div>
          </div>
          {/* Chart & Location-Based Analytics */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* Trend Chart (Glow Gradient) */}
            <div className="lg:col-span-2 rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-5 h-80 shadow-sm flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300">Temporal Crime Intensity</h3>
                <span className="text-[10px] text-slate-400 font-medium">Monthly incident distribution</span>
              </div>
              <div className="flex-1 min-h-0">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={trend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                    <defs>
                      <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.4} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0.0} />
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
                    <Area type="monotone" dataKey="count" stroke="#3b82f6" strokeWidth={2.5} fillOpacity={1} fill="url(#colorCount)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>
            {/* Location-Based Analytics Card */}
            <div className="rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel p-5 h-80 shadow-sm flex flex-col">
              <h3 className="text-sm font-semibold text-slate-700 dark:text-slate-300 mb-3">Top Incident Hotspots</h3>
              <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                {topAreas.slice(0, 5).map((item, idx) => {
                  // Calculate percentage contribution
                  const pct = totalIncidents > 0 ? ((item.count / totalIncidents) * 100).toFixed(1) : "0";
                  // Simple dynamic risk tag
                  const rank = idx + 1;
                  const labelColor = rank === 1 ? "bg-red-500/10 text-red-500 border border-red-500/20" : rank <= 3 ? "bg-amber-500/10 text-amber-500 border border-amber-500/20" : "bg-slate-500/10 text-slate-400 border border-slate-500/10";
                  
                  return (
                    <div key={item.area} className="flex items-center justify-between p-2 rounded-lg bg-slate-50 dark:bg-surface border border-slate-100 dark:border-border/30">
                      <div>
                        <div className="text-xs font-semibold text-slate-800 dark:text-slate-200">{item.area}</div>
                        <div className="text-[10px] text-slate-400 font-medium">{item.count.toLocaleString()} cases · {pct}% contribution</div>
                      </div>
                      <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${labelColor}`}>
                        Rank #{rank}
                      </span>
                    </div>
                  );
                })}
                {topAreas.length === 0 && (
                  <p className="text-xs text-slate-400 text-center py-12">No records found for current filter.</p>
                )}
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

