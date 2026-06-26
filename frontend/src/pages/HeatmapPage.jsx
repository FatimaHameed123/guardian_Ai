import { useCallback, useEffect, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap } from "react-leaflet";
import { apiHeatmap } from "../api";
import HeatLayer from "../components/HeatLayer";

const TIER_COLOR = { low: "#22c55e", medium: "#eab308", high: "#ef4444" };

function MapTheme({ dark }) {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
  }, [dark, map]);
  return null;
}

export default function HeatmapPage({ dark }) {
  const [points, setPoints] = useState([]);
  const [meta, setMeta] = useState({ total: 0, areas: [], crime_types: [] });
  const [filters, setFilters] = useState({ area: "", crime_type: "", date_from: "", date_to: "" });
  const [legend, setLegend] = useState({});
  const [loading, setLoading] = useState(false);

  const load = useCallback((refresh = false) => {
    setLoading(true);
    const params = Object.fromEntries(
      Object.entries(filters).filter(([, v]) => v)
    );
    if (refresh) params.refresh = "1";
    apiHeatmap(params)
      .then((d) => {
        setPoints(d.points || []);
        setLegend(d.legend || {});
        setMeta({
          total: d.total || 0,
          live: d.live_incidents || 0,
          areas: d.areas || [],
          crime_types: d.crime_types || [],
        });
      })
      .finally(() => setLoading(false));
  }, [filters]);

  useEffect(() => {
    load();
    const id = setInterval(() => load(true), 60000);
    return () => clearInterval(id);
  }, [load]);

  const tileUrl = dark
    ? "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
    : "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

  return (
    <div className="flex flex-col gap-4 -m-2 lg:-m-4">
      <div className="flex flex-wrap items-end gap-3 p-4 rounded-xl border border-slate-200 dark:border-border bg-white dark:bg-panel shadow-sm">
        <div>
          <label className="text-[10px] uppercase tracking-wide text-slate-400">Area</label>
          <select
            className="block mt-1 px-3 py-2 text-sm rounded-lg border dark:border-border dark:bg-surface min-w-[140px]"
            value={filters.area}
            onChange={(e) => setFilters({ ...filters, area: e.target.value })}
          >
            <option value="">All areas</option>
            {meta.areas.map((a) => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wide text-slate-400">Crime type</label>
          <select
            className="block mt-1 px-3 py-2 text-sm rounded-lg border dark:border-border dark:bg-surface min-w-[180px]"
            value={filters.crime_type}
            onChange={(e) => setFilters({ ...filters, crime_type: e.target.value })}
          >
            <option value="">All types</option>
            {meta.crime_types.slice(0, 40).map((c) => (
              <option key={c} value={c}>{c.length > 36 ? `${c.slice(0, 36)}…` : c}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wide text-slate-400">From</label>
          <input type="date" className="block mt-1 px-3 py-2 text-sm rounded-lg border dark:border-border dark:bg-surface" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} />
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-wide text-slate-400">To</label>
          <input type="date" className="block mt-1 px-3 py-2 text-sm rounded-lg border dark:border-border dark:bg-surface" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} />
        </div>
        <button onClick={() => load(true)} disabled={loading} className="px-4 py-2 text-sm rounded-lg bg-slate-900 dark:bg-accent text-white disabled:opacity-50">
          {loading ? "Loading…" : "Apply filters"}
        </button>
        <div className="ml-auto text-right">
          <p className="text-xs text-slate-500">{meta.total.toLocaleString()} incidents · {meta.live} live DB</p>
          <div className="flex items-center gap-3 mt-1 text-[10px]">
            {Object.entries(legend).map(([k, v]) => (
              <span key={k} className="flex items-center gap-1 text-slate-500">
                <span className="w-2.5 h-2.5 rounded-full" style={{ background: v.color }} />
                {v.label}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="h-[calc(100vh-200px)] min-h-[480px] rounded-xl border border-slate-200 dark:border-border overflow-hidden shadow-sm">
        <MapContainer center={[34.05, -118.25]} zoom={10} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
          <TileLayer url={tileUrl} attribution="&copy; OpenStreetMap, CARTO" />
          <MapTheme dark={dark} />
          <HeatLayer points={points} />
          {points.map((p, i) => (
            <CircleMarker
              key={`${p.area}-${i}`}
              center={[p.lat, p.lng]}
              radius={6 + (p.intensity || 0.3) * 8}
              pathOptions={{
                color: TIER_COLOR[p.tier] || "#64748b",
                fillColor: TIER_COLOR[p.tier],
                fillOpacity: 0.35,
                weight: 1,
              }}
            >
              <Popup>
                <strong>{p.area}</strong><br />
                Incidents: {p.count}<br />
                Tier: {p.tier}<br />
                Top: {p.top_crime}
                {p.live_count > 0 && <><br />Live cases: {p.live_count}</>}
              </Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </div>
  );
}
