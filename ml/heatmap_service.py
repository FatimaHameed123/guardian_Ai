"""
Geospatial heatmap aggregation from historical CSV + live SQLite cases.
Uses area -> latitude/longitude mapping (no schema changes).
"""
from __future__ import annotations

import random
import sqlite3
from functools import lru_cache
from pathlib import Path

import pandas as pd

from area_coordinates import AREA_COORDINATES, DEFAULT_COORDINATES

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = ROOT / "Professional_Cleaned_Crime_Data.csv"
DEFAULT_DB = ROOT / "CriminalInvestigation_Secured.db"

def invalidate_heatmap_cache() -> None:
    """Clear cached frames after new incidents are stored."""
    _load_combined_frame.cache_clear()

def _db_mtime(db_path: Path) -> float:
    return db_path.stat().st_mtime if db_path.exists() else 0.0

def _load_live_cases(db_path: Path) -> pd.DataFrame:
    if not db_path.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT area AS Area_Name, crime_type AS Crime_Category, created_at AS Incident_Date
            FROM Criminal_Cases
            """
        ).fetchall()
    except sqlite3.Error:
        return pd.DataFrame()
    finally:
        conn.close()

    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows, columns=["Area_Name", "Crime_Category", "Incident_Date"])
    df["Incident_Date"] = pd.to_datetime(df["Incident_Date"], errors="coerce")
    df["Crime_Year"] = df["Incident_Date"].dt.year
    df["Crime_Month"] = df["Incident_Date"].dt.month
    df["source"] = "live_db"
    return df.dropna(subset=["Area_Name"])

@lru_cache(maxsize=4)
def _load_combined_frame(csv_path: str, db_path: str, db_mtime: float) -> pd.DataFrame:
    path = Path(csv_path)
    frames: list[pd.DataFrame] = []

    if path.exists():
        csv_df = pd.read_csv(
            path,
            usecols=[
                "Area_Name",
                "Crime_Category",
                "Incident_Date",
                "Crime_Year",
                "Crime_Month",
            ],
        )
        csv_df["Incident_Date"] = pd.to_datetime(csv_df["Incident_Date"], errors="coerce")
        csv_df["source"] = "historical"
        frames.append(csv_df.dropna(subset=["Area_Name"]))

    live = _load_live_cases(Path(db_path))
    if not live.empty:
        frames.append(live)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)

def _intensity_tier(count: int, p33: float, p66: float) -> str:
    if count >= p66:
        return "high"
    if count >= p33:
        return "medium"
    return "low"

def get_heatmap_points(
    *,
    csv_path: Path | str | None = None,
    db_path: Path | str | None = None,
    area: str | None = None,
    crime_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    max_points: int = 12000,
    grid_precision: int = 3,
    refresh: bool = False,
) -> dict:
    """
    Return heatmap points for Leaflet heat layer.
    Each point: lat, lng, intensity (0-1), tier (low/medium/high), area, count
    """
    if refresh:
        invalidate_heatmap_cache()

    csv_path = str(csv_path or DEFAULT_CSV)
    db_path = str(db_path or DEFAULT_DB)
    db_mtime = _db_mtime(Path(db_path))

    df = _load_combined_frame(csv_path, db_path, db_mtime)
    if df.empty:
        return {"status": "ok", "points": [], "total": 0, "legend": _legend(), "areas": [], "crime_types": []}

    if area:
        df = df[df["Area_Name"].str.lower() == area.lower()]
    if crime_type:
        df = df[df["Crime_Category"].str.contains(crime_type, case=False, na=False)]
    if date_from:
        df = df[df["Incident_Date"] >= pd.to_datetime(date_from)]
    if date_to:
        df = df[df["Incident_Date"] <= pd.to_datetime(date_to)]

    if df.empty:
        return {"status": "ok", "points": [], "total": 0, "legend": _legend(), "areas": [], "crime_types": []}

    # Per-area aggregation with lat/lng from existing coordinate map
    records = []
    for area_name, group in df.groupby("Area_Name"):
        lat, lng = AREA_COORDINATES.get(area_name, DEFAULT_COORDINATES)
        count = len(group)
        records.append({
            "area": area_name,
            "lat": round(lat, grid_precision),
            "lng": round(lng, grid_precision),
            "count": count,
            "live_count": int((group["source"] == "live_db").sum()) if "source" in group.columns else 0,
            "top_crime": group["Crime_Category"].mode().iloc[0] if len(group) else "Unknown",
        })

    grid = pd.DataFrame(records)
    p33 = grid["count"].quantile(0.33)
    p66 = grid["count"].quantile(0.66)
    max_count = grid["count"].max() or 1

    points = []
    rng = random.Random(42)
    for _, row in grid.iterrows():
        tier = _intensity_tier(int(row["count"]), p33, p66)
        intensity = min(1.0, row["count"] / max_count)
        # Spread density visually within area bounds
        for _ in range(min(3, max(1, int(row["count"] // 5000) + 1))):
            jitter_lat = row["lat"] + rng.uniform(-0.012, 0.012)
            jitter_lng = row["lng"] + rng.uniform(-0.012, 0.012)
            points.append({
                "lat": round(jitter_lat, 5),
                "lng": round(jitter_lng, 5),
                "intensity": round(float(intensity), 3),
                "tier": tier,
                "area": row["area"],
                "count": int(row["count"]),
                "live_count": int(row.get("live_count", 0)),
                "top_crime": row["top_crime"],
            })

    if len(points) > max_points:
        step = max(1, len(points) // max_points)
        points = points[::step][:max_points]

    all_areas = sorted(_load_combined_frame(csv_path, db_path, db_mtime)["Area_Name"].unique().tolist())
    crime_types = sorted(df["Crime_Category"].unique().tolist())[:80]

    return {
        "status": "ok",
        "points": points,
        "total": int(len(df)),
        "live_incidents": int((df["source"] == "live_db").sum()) if "source" in df.columns else 0,
        "areas": all_areas,
        "crime_types": crime_types,
        "legend": _legend(),
    }

def _legend() -> dict:
    return {
        "low": {"color": "#22c55e", "label": "Low density"},
        "medium": {"color": "#eab308", "label": "Medium density"},
        "high": {"color": "#ef4444", "label": "High density"},
    }

def get_analytics_summary(
    csv_path: Path | str | None = None,
    db_path: Path | str | None = None,
    area: str | None = None,
    crime_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """Dashboard stats from combined CSV + live DB with filters."""
    csv_path = str(csv_path or DEFAULT_CSV)
    db_path = str(db_path or DEFAULT_DB)
    df = _load_combined_frame(csv_path, db_path, _db_mtime(Path(db_path)))
    
    if not df.empty:
        if area:
            df = df[df["Area_Name"].str.lower() == area.lower()]
        if crime_type:
            df = df[df["Crime_Category"].str.contains(crime_type, case=False, na=False)]
        if date_from:
            df = df[df["Incident_Date"] >= pd.to_datetime(date_from)]
        if date_to:
            df = df[df["Incident_Date"] <= pd.to_datetime(date_to)]

    if df.empty:
        return {
            "status": "ok",
            "total_incidents": 0,
            "high_risk_areas": 0,
            "avg_risk_score": 0,
            "live_incidents": 0,
            "monthly_trend": [],
            "top_areas": [],
            "crime_distribution": [],
            "model_metrics": {},
        }

    area_counts = df.groupby("Area_Name").size()
    high_threshold = area_counts.quantile(0.75) if not area_counts.empty else 0
    high_risk_areas = int((area_counts >= high_threshold).sum()) if not area_counts.empty else 0
    total = int(len(df))
    avg_risk = int(min(100, (area_counts.mean() / (area_counts.max() or 1)) * 100)) if len(area_counts) else 0

    monthly = (
        df.groupby(df["Incident_Date"].dt.to_period("M"))
        .size()
        .reset_index(name="count")
    )
    monthly["month"] = monthly["Incident_Date"].astype(str)

    top_areas = (
        area_counts.reset_index(name="count")
        .rename(columns={"Area_Name": "area"})
        .sort_values("count", ascending=False)
        .head(10)
        .to_dict(orient="records")
    )

    crime_dist = (
        df["Crime_Category"]
        .value_counts()
        .head(12)
        .reset_index()
    )
    crime_dist.columns = ["crime_type", "count"]

    # Load model metrics if they exist
    metrics = {}
    metrics_path = Path(__file__).resolve().parent / "artifacts" / "metrics.json"
    if metrics_path.exists():
        try:
            import json
            with open(metrics_path, "r", encoding="utf-8") as f:
                metrics = json.load(f)
        except Exception:
            pass

    return {
        "status": "ok",
        "total_incidents": total,
        "high_risk_areas": high_risk_areas,
        "avg_risk_score": avg_risk,
        "live_incidents": int((df["source"] == "live_db").sum()) if "source" in df.columns else 0,
        "monthly_trend": monthly[["month", "count"]].tail(24).to_dict(orient="records") if not monthly.empty else [],
        "top_areas": top_areas,
        "crime_distribution": crime_dist.to_dict(orient="records"),
        "model_metrics": metrics,
    }
