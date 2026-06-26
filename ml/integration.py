"""
Backend-compatible model loader for Guardian AI chat_predict integration.
Preserves the existing API contract:
  - model.predict(DataFrame[Area_Encoded, Crime_Year, Crime_Month]) -> incident count estimate
  - le: LabelEncoder for area names
  - area_crime, top_crimes: aggregate tables used in chat replies
"""
from __future__ import annotations

from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder

from chat_predict_service import align_features_for_model
from feature_engineering import inference_features

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

class ChatCompatiblePredictor:
    """
    Wraps the Random Forest classifier so existing Flask routes keep working.
    The /chat_predict route calls predict() with area index + year + month and
    expects a numeric incident-count style output for display.
    """
    def __init__(self, rf_model, encoders: dict, aggregates: dict):
        self.rf_model = rf_model
        self.encoders = encoders
        self.aggregates = aggregates
        self.monthly_avg = aggregates.get("monthly_avg", {})
        self.top_crimes = aggregates.get("top_crimes", {})
        self.area_crime = aggregates.get("area_crime")
        self.monthly_crime = aggregates.get("monthly_crime")
        self.area_classes = list(encoders["area"].classes_)
        self._default_hour = 12
        self._default_dow = 2

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Parameters
        ----------
        X : DataFrame with columns Area_Encoded, Crime_Year, Crime_Month
        Returns
        -------
        ndarray of predicted incident counts (int-compatible floats)
        """
        results = []
        crime_le: LabelEncoder = self.encoders["crime_type"]
        default_crime_idx = int(
            crime_le.transform([crime_le.classes_[0]])[0]
        )
        for _, row in X.iterrows():
            area_idx = int(row["Area_Encoded"])
            year = int(row["Crime_Year"])
            month = int(row["Crime_Month"])
            area_name = self.area_classes[area_idx]
            lat, lon = self._coords_for_area(area_name)
            crime_type = crime_le.classes_[0]
            enhanced = inference_features(
                crime_type=crime_type,
                area=area_name,
                year=year,
                area_crime=self.area_crime,
                monthly_crime=self.monthly_crime,
                reference_year=self.aggregates.get("reference_year", year),
            )
            features = align_features_for_model(
                self.rf_model,
                pd.DataFrame(
                    [
                        {
                            "Crime_Type_Encoded": default_crime_idx,
                            "Area_Encoded": area_idx,
                            "Latitude": lat,
                            "Longitude": lon,
                            "Crime_Year": year,
                            "Hour": self._default_hour,
                            "Day_Of_Week": self._default_dow,
                            "Month": month,
                            **enhanced,
                        }
                    ]
                ),
            )
            proba = self.rf_model.predict_proba(features)[0]
            likely_prob = float(proba[1]) if len(proba) > 1 else float(proba[0])
            baseline = float(self.monthly_avg.get(area_name, 50))
            multiplier = 0.65 + (likely_prob * 0.7)
            results.append(max(1, round(baseline * multiplier)))
        return np.array(results, dtype=float)

    @staticmethod
    def _coords_for_area(area_name: str) -> tuple[float, float]:
        from area_coordinates import AREA_COORDINATES, DEFAULT_COORDINATES
        return AREA_COORDINATES.get(area_name, DEFAULT_COORDINATES)

def load_production_bundle(artifacts_dir: Path | None = None):
    """
    Legacy loader - returns ChatCompatiblePredictor for old predict() calls.
    Prefer load_chat_artifacts() from chat_predict_service for /chat_predict.
    """
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR
    rf_model = joblib.load(artifacts_dir / "crime_rf_model.joblib")
    encoders = joblib.load(artifacts_dir / "label_encoders.joblib")
    aggregates = joblib.load(artifacts_dir / "aggregates.joblib")
    le: LabelEncoder = encoders["area"]
    model = ChatCompatiblePredictor(rf_model, encoders, aggregates)
    area_crime = aggregates["area_crime"]
    top_crimes = aggregates["top_crimes"]
    return model, le, area_crime, top_crimes

def load_rf_artifacts(artifacts_dir: Path | None = None):
    """Load Random Forest model, encoders, and aggregates."""
    from chat_predict_service import load_chat_artifacts
    return load_chat_artifacts(artifacts_dir)

def predict_crime_likelihood(
    crime_type: str,
    area: str,
    latitude: float,
    longitude: float,
    year: int,
    hour: int,
    day_of_week: int,
    month: int,
    artifacts_dir: Path | None = None,
) -> dict:
    """
    Direct classification API for structured prediction requests.
    Returns
    -------
    dict with crime_likely (0/1), probability, and label.
    """
    artifacts_dir = artifacts_dir or ARTIFACTS_DIR
    rf_model = joblib.load(artifacts_dir / "crime_rf_model.joblib")
    encoders = joblib.load(artifacts_dir / "label_encoders.joblib")
    crime_le = encoders["crime_type"]
    area_le = encoders["area"]
    
    crime_cls = crime_type if crime_type in crime_le.classes_ else crime_le.classes_[0]
    area_cls = area if area in area_le.classes_ else area_le.classes_[0]
    
    crime_enc = int(crime_le.transform([crime_cls])[0])
    area_enc = int(area_le.transform([area_cls])[0])
    
    aggregates = {}
    try:
        aggregates = joblib.load(artifacts_dir / "aggregates.joblib")
    except Exception:
        pass
    
    enhanced = inference_features(
        crime_type=crime_cls,
        area=area_cls,
        year=year,
        area_crime=aggregates.get("area_crime"),
        monthly_crime=aggregates.get("monthly_crime"),
        reference_year=aggregates.get("reference_year", year),
    )
    
    features = pd.DataFrame(
        [
            {
                "Crime_Type_Encoded": crime_enc,
                "Area_Encoded": area_enc,
                "Latitude": latitude,
                "Longitude": longitude,
                "Crime_Year": year,
                "Hour": hour,
                "Day_Of_Week": day_of_week,
                "Month": month,
                **enhanced,
            }
        ]
    )
    
    features = align_features_for_model(rf_model, features)
    
    prediction = int(rf_model.predict(features)[0])
    proba = rf_model.predict_proba(features)[0]
    likelihood = float(proba[1]) if len(proba) > 1 else float(proba[0])

    return {
        "crime_likely": prediction,
        "crime_likely_label": "Crime Likely" if prediction == 1 else "Crime Not Likely",
        "probability": round(likelihood, 4),
    }

