"""
Shared feature engineering for training and inference.
Eliminates all forms of data leakage by fitting mappings and aggregates on train data only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

# Crime severity: theft < harassment < violent (0-1 scale)
CRIME_SEVERITY_KEYWORDS = (
    ("theft", 0.35),
    ("stolen", 0.35),
    ("shoplifting", 0.4),
    ("burglary", 0.5),
    ("vandalism", 0.45),
    ("fraud", 0.55),
    ("harassment", 0.6),
    ("stalking", 0.65),
    ("assault", 0.75),
    ("battery", 0.75),
    ("robbery", 0.85),
    ("weapon", 0.9),
    ("homicide", 1.0),
    ("murder", 1.0),
    ("rape", 0.95),
    ("kidnap", 0.95),
    ("arson", 0.8),
    ("narcotic", 0.7),
)

ENHANCED_FEATURE_COLUMNS = [
    "Crime_Severity",
    "Recent_Weight",
    "Trend_Score",
]

def crime_severity_score(crime_type: str) -> float:
    cl = str(crime_type).lower()
    scores = [w for k, w in CRIME_SEVERITY_KEYWORDS if k in cl]
    return max(scores) if scores else 0.5

def compute_recent_weight(years: pd.Series, reference_year: int | None = None) -> pd.Series:
    """Higher weight for more recent incidents (exponential decay)."""
    ref = int(reference_year if reference_year is not None else years.max())
    age = (ref - years.fillna(ref)).clip(lower=0)
    return np.exp(-0.35 * age).astype(float)

def compute_area_frequency_norm(
    df: pd.DataFrame, 
    area_col: str = "Area_Name", 
    area_freq_map: dict[str, float] | None = None
) -> tuple[pd.Series, dict[str, float]]:
    """Compute normalized area frequency using training-set distribution."""
    if area_freq_map is not None:
        # Inference or validation phase using pre-computed mapping
        series = df[area_col].map(area_freq_map).fillna(0.3).astype(float)
        return series, area_freq_map
    # Training phase: compute mapping
    counts = df[area_col].value_counts()
    mx = counts.max() or 1
    mapping = (counts / mx).to_dict()
    series = df[area_col].map(mapping).fillna(0.3).astype(float)
    return series, mapping

def _get_preceding_months(year: int, month: int) -> list[tuple[int, int]]:
    """Return the 3 months preceding the given year and month."""
    res = []
    for i in range(1, 4):
        nm = month - i
        ny = year
        while nm <= 0:
            nm += 12
            ny -= 1
        res.append((ny, nm))
    return res

def compute_trend_scores(
    df: pd.DataFrame, 
    monthly_crime: pd.DataFrame | dict | None = None
) -> tuple[pd.Series, pd.DataFrame]:
    """
    Per-row trend score. Computes the trend from the 3 months preceding each incident.
    Uses only training set aggregates to avoid target/temporal leakage.
    """
    # 1. Standardize monthly crime counts to a lookup dictionary
    count_dict = {}
    
    if monthly_crime is None:
        # Training phase: compute monthly counts from df itself
        monthly = (
            df.groupby(["Area_Name", "Crime_Year", "Month"])
            .size()
            .reset_index(name="Crime_Count")
        )
    elif isinstance(monthly_crime, pd.DataFrame):
        # Validation or retraining phase: use passed DataFrame
        monthly = monthly_crime.copy()
        if "Crime_Month" in monthly.columns:
            monthly = monthly.rename(columns={"Crime_Month": "Month"})
    else:
        # Passed dictionary
        monthly = None
        count_dict = monthly_crime

    if monthly is not None:
        count_dict = monthly.set_index(["Area_Name", "Crime_Year", "Month"])["Crime_Count"].to_dict()
        # Also construct a monthly dataframe for saving in aggregates later
        monthly_crime_df = (
            df.groupby(["Area_Name", "Crime_Year", "Month"])
            .size()
            .reset_index(name="Crime_Count")
            .rename(columns={"Month": "Crime_Month"})
            .sort_values(["Area_Name", "Crime_Year", "Crime_Month"])
        )
    else:
        monthly_crime_df = pd.DataFrame()

    # 2. Get unique combinations of (Area_Name, Crime_Year, Month) in the current dataframe to optimize speed
    keys = df[["Area_Name", "Crime_Year", "Month"]].drop_duplicates()
    
    # 3. For each unique combination, compute the trend score using preceding months
    trend_map = {}
    for _, row in keys.iterrows():
        area = row["Area_Name"]
        year = int(row["Crime_Year"])
        month = int(row["Month"])
        
        preceding = _get_preceding_months(year, month)
        counts = [count_dict.get((area, y, m), 0) for y, m in preceding]
        
        # Fallback if no preceding history is found for this specific time block
        if sum(counts) == 0:
            # Try to grab the latest 3 months in the dictionary for this area
            area_keys = [k for k in count_dict.keys() if k[0] == area]
            if area_keys:
                sorted_keys = sorted(area_keys, key=lambda k: (k[1], k[2]))[-3:]
                counts = [count_dict[k] for k in sorted_keys]
        
        # Ensure counts has exactly 3 elements (pad with zeros)
        while len(counts) < 3:
            counts.append(0)
        
        if sum(counts) == 0:
            trend_map[(area, year, month)] = 0.0
        else:
            # trend = (most_recent_month - oldest_month) / average
            c1, c2, c3 = counts[0], counts[1], counts[2]  # c1 is month-1, c3 is month-3
            delta = c1 - c3
            avg = sum(counts) / len(counts) or 1
            trend_map[(area, year, month)] = float(np.clip(delta / avg, -1.0, 1.0))
            
    # 4. Map the trend scores back to the full dataframe
    series = df.set_index(["Area_Name", "Crime_Year", "Month"]).index.map(trend_map).to_series()
    series.index = df.index
    return series.fillna(0.0).astype(float), monthly_crime_df

def build_risk_target(df: pd.DataFrame, crime_likely: pd.Series) -> pd.Series:
    """Regression target 0-100 aligned with classifier labels and severity."""
    severity = df["Crime_Severity"] if "Crime_Severity" in df.columns else 0.5
    recent = df["Recent_Weight"] if "Recent_Weight" in df.columns else 0.5
    trend = df["Trend_Score"] if "Trend_Score" in df.columns else 0.0
    raw = (
        crime_likely.astype(float) * 50
        + severity * 30
        + recent * 15
        + (trend + 1) * 2.5
    )
    return raw.clip(0, 100).round().astype(int)

def apply_training_features(
    df: pd.DataFrame,
    area_freq_map: dict[str, float] | None = None,
    reference_year: int | None = None,
    historical_monthly_crime: pd.DataFrame | dict | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Add engineered columns used by classifier and risk regressor safely."""
    out = df.copy()
    out["Crime_Severity"] = out["Crime_Category"].map(crime_severity_score)
    
    # Compute/apply Area Frequency Normalization
    freq_series, computed_freq_map = compute_area_frequency_norm(out, area_freq_map=area_freq_map)
    out["Area_Frequency_Norm"] = freq_series
    
    # Compute/apply Recent Weight
    ref_yr = reference_year
    if ref_yr is None:
        ref_yr = int(out["Crime_Year"].max())
    out["Recent_Weight"] = compute_recent_weight(out["Crime_Year"], reference_year=ref_yr)
    
    # Compute/apply Trend Score
    trend_series, computed_monthly_crime = compute_trend_scores(out, monthly_crime=historical_monthly_crime)
    out["Trend_Score"] = trend_series
    
    # Pack up computed aggregates for potential return (needed during train fitting)
    computed_aggregates = {
        "area_freq_map": computed_freq_map,
        "reference_year": ref_yr,
        "historical_monthly_crime": computed_monthly_crime,
    }
    
    return out, computed_aggregates

def inference_features(
    *,
    crime_type: str,
    area: str,
    year: int,
    area_crime: pd.DataFrame | None,
    monthly_crime: pd.DataFrame | None,
    reference_year: int | None = None,
) -> dict[str, float]:
    """Build enhanced feature dict for a single prediction row during inference."""
    severity = crime_severity_score(crime_type)
    
    # 1. Area frequency mapping
    historical_total = 0
    if area_crime is not None and not area_crime.empty:
        row = area_crime[area_crime["Area_Name"] == area]
        if not row.empty:
            historical_total = int(row["Total_Crime_Count"].iloc[0])
    mx = 70000
    if area_crime is not None and not area_crime.empty:
        mx = max(int(area_crime["Total_Crime_Count"].max()), 1)
    area_freq = min(1.0, historical_total / mx) if historical_total else 0.3

    # 2. Recent Weight
    ref = reference_year or year
    recent = float(np.exp(-0.35 * max(0, ref - year)))

    # 3. Dynamic trend lookup
    trend = 0.0
    if monthly_crime is not None and not monthly_crime.empty:
        # Format monthly_crime into a count lookup dictionary
        monthly = monthly_crime.copy()
        if "Crime_Month" in monthly.columns:
            monthly = monthly.rename(columns={"Crime_Month": "Month"})
        
        count_dict = monthly.set_index(["Area_Name", "Crime_Year", "Month"])["Crime_Count"].to_dict()
        
        # We assume month isn't passed directly, so we look at latest tail(3) for the area
        sub = monthly[monthly["Area_Name"] == area].sort_values(["Crime_Year", "Month"])
        if len(sub) >= 2:
            vals = sub["Crime_Count"].tail(3).tolist()
            delta = vals[-1] - vals[0]
            avg = sum(vals) / len(vals) or 1
            trend = float(np.clip(delta / avg, -1.0, 1.0))

    return {
        "Crime_Severity": severity,
        "Recent_Weight": recent,
        "Trend_Score": trend,
    }
