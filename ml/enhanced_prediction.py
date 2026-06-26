"""
Enhanced multi-output prediction layer on top of existing Random Forest model.
Does NOT replace the RF pipeline — extends outputs only.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from feature_engineering import crime_severity_score

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"


def _load_risk_regressor(artifacts_dir: Path | None = None):
    path = (artifacts_dir or ARTIFACTS_DIR) / "crime_risk_rf_model.joblib"
    if path.exists():
        return joblib.load(path)
    return None


def _hour_risk_factor(hour: int) -> float:
    if 22 <= hour or hour <= 4:
        return 1.15
    if 18 <= hour <= 21:
        return 1.05
    if 6 <= hour <= 10:
        return 0.85
    return 1.0


def compute_trend(area: str, month: int, monthly_crime: pd.DataFrame) -> str:
    """Increasing / Decreasing / Stable from area monthly history."""
    if monthly_crime is None or monthly_crime.empty:
        return "Stable"
    sub = monthly_crime[monthly_crime["Area_Name"] == area].sort_values(
        ["Crime_Year", "Crime_Month"]
    )
    if len(sub) < 2:
        return "Stable"
    recent = sub.tail(3)["Crime_Count"].tolist()
    if len(recent) < 2:
        return "Stable"
    delta = recent[-1] - recent[0]
    avg = sum(recent) / len(recent)
    if avg == 0:
        return "Stable"
    pct = delta / avg
    if pct > 0.08:
        return "Increasing"
    if pct < -0.08:
        return "Decreasing"
    return "Stable"


def _top_feature_names(rf_model, features: pd.DataFrame, limit: int = 2) -> list[str]:
    if not hasattr(rf_model, "feature_importances_"):
        return []
    cols = list(features.columns)
    imp = rf_model.feature_importances_
    order = imp.argsort()[::-1][:limit]
    return [cols[i].replace("_", " ").lower() for i in order]


def build_explanation(
    area: str,
    crime_type: str,
    hour: int,
    probability: float,
    risk_level: str,
    trend: str,
    historical_total: int,
    risk_score: int,
    rf_model=None,
    features: pd.DataFrame | None = None,
    reg_score: float | None = None,
) -> str:
    """Human-readable explanation for the prediction."""
    parts = []
    parts.append(
        f"{area} is assessed as {risk_level.lower()} risk ({risk_score}/100) for "
        f"{crime_type.lower()}."
    )

    if 22 <= hour or hour <= 4:
        parts.append("Late-night hours historically correlate with higher incident rates.")
    elif 6 <= hour <= 10:
        parts.append("Morning hours typically show comparatively lower risk.")

    sev = crime_severity_score(crime_type)
    if sev >= 0.75:
        parts.append("This crime category is weighted as high severity in the model.")
    elif sev <= 0.45:
        parts.append("This category has lower severity weighting than violent offenses.")

    if historical_total > 55000:
        parts.append(f"The area has high historical volume ({historical_total:,} incidents).")
    elif historical_total < 40000 and historical_total > 0:
        parts.append(f"Historical volume is moderate ({historical_total:,} incidents).")

    if trend == "Increasing":
        parts.append("Recent monthly trends indicate rising activity in this area.")
    elif trend == "Decreasing":
        parts.append("Recent monthly trends show declining activity.")

    parts.append(f"Classifier likelihood: {probability * 100:.1f}%.")
    if reg_score is not None:
        parts.append(f"Risk regression estimate: {reg_score:.0f}/100.")

    tops = _top_feature_names(rf_model, features) if rf_model is not None and features is not None else []
    if tops:
        parts.append(f"Primary drivers: {', '.join(tops)}.")

    return " ".join(parts)


def compute_enhanced_assessment(
    rf_model,
    features: pd.DataFrame,
    *,
    area: str,
    crime_type: str,
    hour: int,
    month: int,
    probability: float,
    crime_likely: int,
    historical_total: int,
    monthly_crime: pd.DataFrame | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Extend base RF probability with industry-style outputs (0–100 risk score, trend, explanation).
    """
    proba = rf_model.predict_proba(features)[0]
    confidence = float(max(proba)) * 100

    severity = crime_severity_score(crime_type)
    hour_factor = _hour_risk_factor(hour)
    hist_factor = min(1.0, historical_total / 70000) if historical_total else 0.3

    risk_reg = _load_risk_regressor(artifacts_dir)
    reg_score: float | None = None
    if risk_reg is not None:
        try:
            reg_score = float(risk_reg.predict(features)[0])
            reg_score = max(0.0, min(100.0, reg_score))
        except ValueError:
            reg_score = None

    heuristic = (
        probability * 50
        + severity * 22
        + (hour_factor - 1) * 12
        + hist_factor * 10
    )
    if reg_score is not None:
        risk_score = int(max(0, min(100, round(0.55 * reg_score + 0.45 * heuristic))))
    else:
        risk_score = int(max(0, min(100, round(heuristic))))

    if risk_score >= 65:
        risk_level = "High"
    elif risk_score >= 35:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    trend = compute_trend(area, month, monthly_crime)
    explanation = build_explanation(
        area,
        crime_type,
        hour,
        probability,
        risk_level,
        trend,
        historical_total,
        risk_score,
        rf_model,
        features,
        reg_score,
    )

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "confidence_score": round(confidence, 1),
        "trend_indicator": trend,
        "explanation": explanation,
        "crime_likely": crime_likely,
        "crime_likely_label": "Crime Likely" if crime_likely else "Crime Not Likely",
        "probability": round(probability, 4),
        "model": "RandomForest+RiskRegressor" if reg_score is not None else "RandomForest",
    }
