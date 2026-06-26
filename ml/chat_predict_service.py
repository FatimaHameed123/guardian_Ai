"""
Intelligent crime-risk chatbot powered by the trained Random Forest model.

Used by Flask /chat_predict — keeps backward-compatible `reply` HTML plus structured JSON.
"""

from __future__ import annotations

import re
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path
from typing import Any, Callable

import joblib
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from area_coordinates import AREA_COORDINATES, DEFAULT_COORDINATES
from enhanced_prediction import compute_enhanced_assessment
from feature_engineering import ENHANCED_FEATURE_COLUMNS, inference_features

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

FEATURE_COLUMNS = [
    "Crime_Type_Encoded",
    "Area_Encoded",
    "Latitude",
    "Longitude",
    "Crime_Year",
    "Hour",
    "Day_Of_Week",
    "Month",
    *ENHANCED_FEATURE_COLUMNS,
]

# User-friendly area aliases (not all in LAPD dataset)
AREA_ALIASES = {
    "downtown": "Central",
    "downtown la": "Central",
    "downtown los angeles": "Central",
    "central la": "Central",
    "central los angeles": "Central",
    "venice": "Pacific",
    "venice beach": "Pacific",
    "north hollywood": "N Hollywood",
    "n hollywood": "N Hollywood",
    "77th street": "77Th Street",
    "77th": "77Th Street",
    "west la": "West La",
    "west los angeles": "West La",
    "van nuys": "Van Nuys",
    "hollywood hills": "Hollywood Hills",
}

# Spoken crime keywords -> substrings matched against trained crime categories
CRIME_KEYWORDS = {
    "robbery": ["robbery"],
    "theft": ["theft", "stolen", "shoplifting"],
    "burglary": ["burglary"],
    "assault": ["assault", "battery"],
    "vehicle": ["vehicle"],
    "vandalism": ["vandalism"],
    "arson": ["arson"],
    "fraud": ["fraud", "identity"],
    "weapon": ["weapon", "gun"],
    "homicide": ["homicide", "murder"],
    "kidnap": ["kidnap"],
    "drug": ["narcotic", "drug"],
    "sex": ["rape", "sex", "peeping"],
    "stalking": ["stalking"],
    "threat": ["threat"],
}

MONTH_NAMES = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

TIME_PHRASES = {
    "midnight": 0, "late night": 23, "night": 22, "at night": 22,
    "evening": 19, "dusk": 18, "morning": 8, "afternoon": 14,
    "noon": 12, "lunch": 12, "early morning": 6, "sunrise": 6, "sunset": 18,
}


def load_chat_artifacts(artifacts_dir: Path | None = None) -> dict[str, Any]:
    """Load model, encoders, and aggregates for chat + legacy globals."""
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR
    encoders = joblib.load(artifacts_dir / "label_encoders.joblib")
    aggregates = joblib.load(artifacts_dir / "aggregates.joblib")
    risk_path = artifacts_dir / "crime_risk_rf_model.joblib"
    return {
        "rf_model": joblib.load(artifacts_dir / "crime_rf_model.joblib"),
        "risk_model": joblib.load(risk_path) if risk_path.exists() else None,
        "encoders": encoders,
        "aggregates": aggregates,
        "artifacts_dir": artifacts_dir,
        "area_crime": aggregates["area_crime"],
        "top_crimes": aggregates["top_crimes"],
        "monthly_avg": aggregates.get("monthly_avg", {}),
        "le": encoders["area"],
        "crime_classes": list(encoders["crime_type"].classes_),
        "area_classes": list(encoders["area"].classes_),
    }


def extract_area(query: str, area_classes: list[str]) -> tuple[str | None, str | None]:
    """
    Detect LAPD area from user text.

    Returns (canonical_area, warning_message).
    """
    q = query.lower().strip()
    if not q:
        return None, None

    for alias, canonical in sorted(AREA_ALIASES.items(), key=lambda x: -len(x[0])):
        if alias in q and canonical in area_classes:
            return canonical, None

    matches = [a for a in area_classes if a.lower() in q]
    if matches:
        return max(matches, key=len), None

    tokens = re.findall(r"[a-z0-9]+", q)
    for token in tokens:
        if len(token) < 4:
            continue
        close = get_close_matches(token, [a.lower() for a in area_classes], n=1, cutoff=0.82)
        if close:
            idx = [a.lower() for a in area_classes].index(close[0])
            return area_classes[idx], f'Interpreted "{token}" as area {area_classes[idx]}.'

    return None, None


def extract_crime_type(query: str, crime_classes: list[str]) -> tuple[str, str | None]:
    """
    Map user text to a trained crime category.

    Returns (crime_type, warning_message).
    """
    q = query.lower()
    for keyword, patterns in CRIME_KEYWORDS.items():
        if keyword not in q:
            continue
        for crime in crime_classes:
            cl = crime.lower()
            if any(p in cl for p in patterns):
                return crime, None

    for crime in crime_classes:
        short = crime.split("-")[0].split("(")[0].strip().lower()
        if len(short) >= 5 and short in q:
            return crime, None

    default = crime_classes[0]
    if any(w in q for w in CRIME_KEYWORDS):
        close = get_close_matches(q[:40], crime_classes, n=1, cutoff=0.4)
        if close:
            return close[0], f'Using closest known crime type: {close[0]}.'
    return default, f'Crime type not specified — using regional baseline: {default}.'


def extract_hour(query: str) -> tuple[int, str | None]:
    """Parse hour 0-23 from natural language."""
    q = query.lower()

    match = re.search(r"(\d{1,2})\s*(?::(\d{2}))?\s*(am|pm)", q)
    if match:
        hour = int(match.group(1)) % 12
        if match.group(3) == "pm":
            hour += 12
        if match.group(3) == "am" and int(match.group(1)) == 12:
            hour = 0
        return min(23, max(0, hour)), None

    match = re.search(r"\b(\d{1,2})\s*(?:o'?clock)?\s*(pm|am)\b", q)
    if match:
        h = int(match.group(1)) % 12
        if match.group(2) == "pm":
            h += 12
        return min(23, max(0, h)), None

    match = re.search(r"\bat\s+(\d{1,2})\b", q)
    if match:
        h = int(match.group(1))
        if "pm" in q or "night" in q or h < 12 and ("evening" in q or "night" in q):
            if h < 12:
                h += 12
        return min(23, max(0, h)), None

    for phrase, hour in TIME_PHRASES.items():
        if phrase in q:
            return hour, None

    return datetime.now().hour, "Time not specified — using current hour."


def extract_month(query: str) -> tuple[int, str | None]:
    """Parse month 1-12 from query or use current month."""
    q = query.lower()
    for name, num in MONTH_NAMES.items():
        if re.search(rf"\b{re.escape(name)}\b", q):
            return num, None
    return datetime.now().month, None


def encode_crime_type(crime_type: str, crime_le: LabelEncoder) -> tuple[int, str | None]:
    if crime_type in crime_le.classes_:
        return int(crime_le.transform([crime_type])[0]), None
    default = crime_le.classes_[0]
    return int(crime_le.transform([default])[0]), f'Unknown crime type — defaulted to {default}.'


def encode_area(area: str, area_le: LabelEncoder) -> tuple[int, str | None]:
    if area in area_le.classes_:
        return int(area_le.transform([area])[0]), None
    close = get_close_matches(area, list(area_le.classes_), n=1, cutoff=0.6)
    if close:
        return int(area_le.transform([close[0]])[0]), f'Area approximated as {close[0]}.'
    default = area_le.classes_[0]
    return int(area_le.transform([default])[0]), f'Unknown area — defaulted to {default}.'


def build_feature_vector(
    crime_type: str,
    area: str,
    crime_le: LabelEncoder,
    area_le: LabelEncoder,
    year: int | None = None,
    hour: int | None = None,
    day_of_week: int | None = None,
    month: int | None = None,
    aggregates: dict | None = None,
) -> tuple[pd.DataFrame, dict[str, Any], list[str]]:
    """
    Build the full feature row for Random Forest predict_proba.

    Returns (feature_df, context_dict, warnings).
    """
    warnings: list[str] = []
    now = datetime.now()
    year = year or now.year
    hour = 12 if hour is None else min(23, max(0, int(hour)))
    month = month or now.month
    day_of_week = day_of_week if day_of_week is not None else now.weekday()

    crime_enc, w1 = encode_crime_type(crime_type, crime_le)
    if w1:
        warnings.append(w1)
    area_enc, w2 = encode_area(area, area_le)
    if w2:
        warnings.append(w2)

    lat, lon = AREA_COORDINATES.get(area, DEFAULT_COORDINATES)

    ref_year = (aggregates or {}).get("reference_year", year)
    enhanced = inference_features(
        crime_type=crime_type,
        area=area,
        year=int(year),
        area_crime=(aggregates or {}).get("area_crime"),
        monthly_crime=(aggregates or {}).get("monthly_crime"),
        reference_year=ref_year,
    )

    row = {
        "Crime_Type_Encoded": crime_enc,
        "Area_Encoded": area_enc,
        "Latitude": lat,
        "Longitude": lon,
        "Crime_Year": int(year),
        "Hour": hour,
        "Day_Of_Week": int(day_of_week),
        "Month": int(month),
        **enhanced,
    }
    context = {
        **row,
        "crime_type": crime_type,
        "area": area,
        "latitude": lat,
        "longitude": lon,
    }
    return pd.DataFrame([row], columns=FEATURE_COLUMNS), context, warnings


def probability_to_risk(probability: float) -> tuple[str, str]:
    """Map model probability to risk tier and emoji label."""
    if probability >= 0.65:
        return "High Risk", "🚨"
    if probability >= 0.35:
        return "Medium Risk", "⚠️"
    return "Low Risk", "✅"


def compute_safety_score(probability: float, historical_total: int, max_hist: int = 70000) -> int:
    """Blend ML probability with historical volume for 0-100 safety score."""
    ml_component = (1.0 - probability) * 100
    hist_ratio = min(1.0, historical_total / max_hist) if max_hist else 0
    hist_component = (1.0 - hist_ratio) * 100
    return int(max(0, min(100, 0.65 * ml_component + 0.35 * hist_component)))


BASE_FEATURE_COLUMNS = FEATURE_COLUMNS[:8]


def align_features_for_model(model, features: pd.DataFrame) -> pd.DataFrame:
    """Support legacy 8-feature models and new 12-feature models."""
    expected = getattr(model, "n_features_in_", features.shape[1])
    cols = FEATURE_COLUMNS if expected == len(FEATURE_COLUMNS) else BASE_FEATURE_COLUMNS
    return features.reindex(columns=cols, fill_value=0)


def predict_probability(rf_model, features: pd.DataFrame) -> tuple[int, float]:
    """Run predict + predict_proba; return (class, probability of crime likely)."""
    features = align_features_for_model(rf_model, features)
    pred = int(rf_model.predict(features)[0])
    proba = rf_model.predict_proba(features)[0]
    likelihood = float(proba[1]) if len(proba) > 1 else float(proba[0])
    return pred, likelihood


def generate_risk_response(
    *,
    area: str,
    crime_type: str,
    hour: int,
    month: int,
    risk_level: str,
    risk_emoji: str,
    probability: float,
    crime_likely: int,
    safety_score: int,
    historical_total: int,
    top_crime: str,
    predicted_incidents: int,
    live_case: dict | None,
    warnings: list[str],
    extra_note: str = "",
    structured_extras: dict | None = None,
) -> tuple[str, dict[str, Any]]:
    """Build HTML reply (frontend) and structured JSON payload."""
    time_label = datetime.strptime(f"{hour:02d}", "%H").strftime("%I %p").lstrip("0") if hour is not None else "N/A"
    month_name = datetime(2000, month, 1).strftime("%B")

    reply = (
        f"<b>📍 {area} — AI Crime Risk Analysis</b><br>"
        f"{risk_emoji} <b>{risk_level}</b> "
        f"(model confidence: {probability * 100:.1f}%)<br>"
        f"Crime Likely: <b>{'Yes' if crime_likely else 'No'}</b> | "
        f"Safety Score: <b>{safety_score}%</b><br>"
        f"Context: <b>{crime_type}</b> around <b>{time_label}</b> in <b>{month_name}</b><br>"
        f"Historical incidents (2020–2025): <b>{historical_total:,}</b><br>"
        f"Most common crime in area: <b>{top_crime}</b><br>"
        f"🔮 Random Forest estimate: <b>{predicted_incidents}</b> incidents "
        f"(similar conditions)<br>"
    )
    if structured_extras:
        reply += (
            f"<br><b>Risk Score:</b> {structured_extras.get('risk_score', '—')}/100 | "
            f"<b>Trend:</b> {structured_extras.get('trend_indicator', '—')}<br>"
            f"<b>Explanation:</b> {structured_extras.get('explanation', '')}"
        )
    if extra_note:
        reply += f"<br>💡 {extra_note}"
    if warnings:
        reply += "<br><i>" + " | ".join(warnings[:3]) + "</i>"
    if live_case:
        reply += (
            f'<br><br>⚠️ <b>ACTIVE CASE:</b> "{live_case["case_title"]}" — '
            f'{live_case["investigator_name"]}'
        )

    structured = {
        "status": "ok",
        "area": area,
        "crime_type": crime_type,
        "hour": hour,
        "month": month,
        "risk_level": risk_level,
        "risk_emoji": risk_emoji,
        "risk_probability": round(probability, 4),
        "crime_likely": crime_likely,
        "crime_likely_label": "Crime Likely" if crime_likely else "Crime Not Likely",
        "safety_score": safety_score,
        "historical_incidents": historical_total,
        "top_crime": top_crime,
        "predicted_incidents": predicted_incidents,
        "live_case": live_case,
        "model": "RandomForest",
        "warnings": warnings,
    }
    if structured_extras:
        structured.update(structured_extras)
    return reply, structured


def _historical_total(area: str, area_crime: pd.DataFrame) -> int:
    rows = area_crime[area_crime["Area_Name"] == area]["Total_Crime_Count"].values
    return int(rows[0]) if len(rows) else 0


def _predicted_incidents(area: str, probability: float, monthly_avg: dict) -> int:
    baseline = float(monthly_avg.get(area, 50))
    return max(1, round(baseline * (0.55 + probability * 0.9)))


def _find_safest_hour(
    rf_model,
    crime_type: str,
    area: str,
    crime_le: LabelEncoder,
    area_le: LabelEncoder,
    month: int,
    year: int,
    aggregates: dict | None = None,
) -> tuple[int, float]:
    """Compare key hours and return lowest crime-likelihood hour."""
    best_hour, best_prob = 12, 1.0
    for hour in (6, 10, 14, 18, 22, 23):
        features, _, _ = build_feature_vector(
            crime_type, area, crime_le, area_le,
            year=year, hour=hour, month=month,
            aggregates=aggregates,
        )
        _, prob = predict_probability(rf_model, features)
        if prob < best_prob:
            best_prob, best_hour = prob, hour
    return best_hour, best_prob


def process_chat_message(
    user_query: str,
    rf_model,
    encoders: dict,
    aggregates: dict,
    get_live_case: Callable[[str], dict | None] | None = None,
    artifacts_dir: Path | None = None,
) -> dict[str, Any]:
    """
    Main chatbot entry — returns dict with `reply` + structured fields.

    Parameters
    ----------
    get_live_case : optional callback(area) -> {case_title, investigator_name} or None
    """
    query = user_query.strip().lower()
    if not query:
        return {"status": "error", "reply": "Please enter a valid message."}

    area_classes = list(encoders["area"].classes_)
    crime_classes = list(encoders["crime_type"].classes_)
    crime_le = encoders["crime_type"]
    area_le = encoders["area"]
    area_crime = aggregates["area_crime"]
    top_crimes = aggregates["top_crimes"]
    monthly_avg = aggregates.get("monthly_avg", {})
    now = datetime.now()

    if any(re.search(rf"\b{re.escape(w)}\b", query) for w in ("hi", "hello", "hey", "salam", "aoa")):
        return {
            "status": "ok",
            "reply": (
                "👋 Hello! I'm Guardian AI. Ask me things like:<br>"
                "• <i>Robbery risk in Hollywood at 11 PM</i><br>"
                "• <i>Is Downtown safe at night?</i><br>"
                "• <i>Most common crime in Central</i>"
            ),
            "intent": "greeting",
        }

    if "how are you" in query:
        return {
            "status": "ok",
            "reply": "🟢 All systems operational. I can assess crime risk by area, crime type, and time.",
            "intent": "greeting",
        }

    area, area_warn = extract_area(query, area_classes)
    warnings = [area_warn] if area_warn else []

    # Intent: most common crime (area optional)
    if any(p in query for p in ("most common", "common crime", "top crime", "which crime")):
        target = area or "Central"
        if not area:
            warnings.append("No area detected — showing Central LA as example.")
        top = top_crimes.get(target, "Vehicle - Stolen")
        total = _historical_total(target, area_crime)
        reply = (
            f"<b>📊 Crime profile — {target}</b><br>"
            f"The most frequently reported crime is <b>{top}</b>.<br>"
            f"Total historical incidents: <b>{total:,}</b> (2020–2025).<br>"
            f"Ask with a time context for a personalized risk score "
            f"(e.g. <i>theft risk in {target} at night</i>)."
        )
        return {
            "status": "ok",
            "reply": reply,
            "intent": "top_crime",
            "area": target,
            "top_crime": top,
            "historical_incidents": total,
        }

    if not area:
        sample = ", ".join(area_classes[:8])
        return {
            "status": "error",
            "reply": (
                f"❓ I couldn't identify an LA area. Try including a name like: "
                f"<b>{sample}</b><br>"
                f"Examples: <i>Hollywood at night</i>, <i>robbery in Rampart at 11pm</i>"
            ),
            "intent": "missing_area",
            "suggested_areas": area_classes[:12],
        }

    crime_type, crime_warn = extract_crime_type(query, crime_classes)
    if crime_warn:
        warnings.append(crime_warn)

    hour, hour_warn = extract_hour(query)
    if hour_warn:
        warnings.append(hour_warn)

    month, month_warn = extract_month(query)
    if month_warn:
        warnings.append(month_warn)

    extra_note = ""

    # Intent: safest travel time
    if any(p in query for p in ("safe time", "safest time", "best time to travel", "when is it safe")):
        safe_hour, safe_prob = _find_safest_hour(
            rf_model, crime_type, area, crime_le, area_le, month, now.year, aggregates
        )
        hour = safe_hour
        extra_note = (
            f"Based on the model, lower-risk travel around "
            f"{datetime.strptime(f'{safe_hour:02d}', '%H').strftime('%I %p').lstrip('0')} "
            f"(~{safe_prob * 100:.0f}% crime-likelihood score)."
        )

    features, context, build_warnings = build_feature_vector(
        crime_type=crime_type,
        area=area,
        crime_le=crime_le,
        area_le=area_le,
        year=now.year,
        hour=hour,
        month=month,
        aggregates=aggregates,
    )
    warnings.extend(build_warnings)

    crime_likely, probability = predict_probability(rf_model, features)
    risk_level, risk_emoji = probability_to_risk(probability)
    historical_total = _historical_total(area, area_crime)
    safety_score = compute_safety_score(probability, historical_total)
    top_crime = top_crimes.get(area, crime_type)
    predicted_incidents = _predicted_incidents(area, probability, monthly_avg)

    live_case = get_live_case(area) if get_live_case else None

    monthly_crime = aggregates.get("monthly_crime")
    enhanced = compute_enhanced_assessment(
        rf_model,
        align_features_for_model(rf_model, features),
        area=area,
        crime_type=crime_type,
        hour=hour,
        month=month,
        probability=probability,
        crime_likely=crime_likely,
        historical_total=historical_total,
        monthly_crime=monthly_crime,
        artifacts_dir=artifacts_dir,
    )

    reply, structured = generate_risk_response(
        area=area,
        crime_type=crime_type,
        hour=hour,
        month=month,
        risk_level=risk_level,
        risk_emoji=risk_emoji,
        probability=probability,
        crime_likely=crime_likely,
        safety_score=safety_score,
        historical_total=historical_total,
        top_crime=top_crime,
        predicted_incidents=predicted_incidents,
        live_case=live_case,
        warnings=warnings,
        extra_note=extra_note,
        structured_extras=enhanced,
    )

    return {"reply": reply, "intent": "risk_analysis", **structured}
