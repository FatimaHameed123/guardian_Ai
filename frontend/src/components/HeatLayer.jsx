import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.heat";

export default function HeatLayer({ points }) {
  const map = useMap();

  useEffect(() => {
    if (!points?.length) return undefined;
    if (typeof L.heatLayer !== "function") return undefined;

    const heatData = points.map((p) => [p.lat, p.lng, p.intensity ?? 0.5]);
    const layer = L.heatLayer(heatData, {
      radius: 28,
      blur: 18,
      maxZoom: 14,
      minOpacity: 0.35,
      gradient: {
        0.2: "#22c55e",
        0.45: "#84cc16",
        0.55: "#eab308",
        0.75: "#f97316",
        1.0: "#ef4444",
      },
    });
    layer.addTo(map);

    return () => {
      map.removeLayer(layer);
    };
  }, [map, points]);

  return null;
}