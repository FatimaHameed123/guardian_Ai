"""
Train Random Forest Classifier for crime likelihood prediction.
Target: 1 = Crime Likely, 0 = Crime Not Likely.
Train leakage-free classification and regression models for crime likelihood.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import (
    RandomForestClassifier,
    RandomForestRegressor,
    ExtraTreesClassifier,
    GradientBoostingClassifier,
)
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
    mean_absolute_error,
    r2_score,
)
from sklearn.model_selection import RandomizedSearchCV, train_test_split, TimeSeriesSplit
from sklearn.preprocessing import LabelEncoder

from area_coordinates import AREA_COORDINATES, DEFAULT_COORDINATES
from feature_engineering import (
    ENHANCED_FEATURE_COLUMNS,
    apply_training_features,
    build_risk_target,
)

# Optional XGBoost import
try:
    from xgboost import XGBClassifier, XGBRegressor
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA = ROOT / "Professional_Cleaned_Crime_Data.csv"
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

def parse_time_hour(value) -> int:
    """Parse Incident_Time (HHMM int or string) into hour 0-23."""
    if pd.isna(value):
        return 12
    text = str(value).strip().replace(":", "")
    if not text:
        return 12
    try:
        numeric = int(float(text))
    except ValueError:
        return 12
    if numeric >= 100:
        return min(23, max(0, numeric // 100))
    return min(23, max(0, numeric))

def load_and_clean(csv_path: Path, max_rows: int | None = None) -> pd.DataFrame:
    print(f"Loading dataset: {csv_path}")
    df = pd.read_csv(csv_path, nrows=max_rows)
    initial_rows = len(df)
    print(f"  Loaded {initial_rows:,} rows")

    df = df.drop_duplicates()
    print(f"  Removed {initial_rows - len(df):,} duplicate rows")

    df["Incident_Date"] = pd.to_datetime(df["Incident_Date"], errors="coerce")
    df["Incident_Time"] = df["Incident_Time"].astype(str)
    df["Area_Name"] = df["Area_Name"].fillna("Unknown").astype(str).str.strip()
    df["Crime_Category"] = df["Crime_Category"].fillna("Unknown").astype(str).str.strip()
    df["Victim_Gender"] = df["Victim_Gender"].fillna("U")
    df["Premises_Description"] = df["Premises_Description"].fillna("Unknown")

    df = df.dropna(subset=["Incident_Date", "Area_Name", "Crime_Category", "Area_Risk_Level"])
    print(f"  Rows after cleaning: {len(df):,}")
    return df

def build_density_mapping(df_train: pd.DataFrame) -> tuple[dict, float]:
    """Compute incident densities and 60th percentile threshold on training set ONLY."""
    density_series = df_train.groupby(["Area_Name", "Month", "Hour", "Day_Of_Week"])["Case_ID"].transform("count")
    threshold = float(density_series.quantile(0.60)) if not density_series.empty else 0.0
    grouped = df_train.groupby(["Area_Name", "Month", "Hour", "Day_Of_Week"]).size().to_dict()
    return grouped, threshold

def compute_crime_likely_label(df: pd.DataFrame, density_map: dict, threshold: float) -> pd.Series:
    """Label Y: 1 = Crime Likely, 0 = Crime Not Likely, using training density map and threshold."""
    keys = list(zip(df["Area_Name"], df["Month"], df["Hour"], df["Day_Of_Week"]))
    density_values = [density_map.get(k, 0) for k in keys]
    density = pd.Series(density_values, index=df.index).astype(float)
    return (density >= threshold).astype(int)

def fit_label_encoders(df_train: pd.DataFrame) -> dict[str, LabelEncoder]:
    encoders = {
        "crime_type": LabelEncoder(),
        "area": LabelEncoder(),
    }
    encoders["crime_type"].fit(df_train["Crime_Type"])
    encoders["area"].fit(df_train["Area_Location"])
    return encoders

def transform_categories(df: pd.DataFrame, encoders: dict) -> pd.DataFrame:
    out = df.copy()
    
    crime_le = encoders["crime_type"]
    default_crime = crime_le.classes_[0]
    out["Crime_Type_Encoded"] = out["Crime_Type"].map(
        lambda val: crime_le.transform([val])[0] if val in crime_le.classes_ else crime_le.transform([default_crime])[0]
    ).astype(int)
    
    area_le = encoders["area"]
    default_area = area_le.classes_[0]
    out["Area_Encoded"] = out["Area_Location"].map(
        lambda val: area_le.transform([val])[0] if val in area_le.classes_ else area_le.transform([default_area])[0]
    ).astype(int)
    
    return out

def build_aggregates(df_train: pd.DataFrame, area_encoder: LabelEncoder) -> dict:
    """Statistics used by the chatbot APIs, derived from training data ONLY."""
    area_crime = df_train.groupby("Area_Name").size().reset_index(name="Total_Crime_Count")
    
    monthly_crime = (
        df_train.groupby(["Area_Name", "Crime_Year", "Month"])
        .size()
        .reset_index(name="Crime_Count")
        .rename(columns={"Month": "Crime_Month"})
        .sort_values(["Area_Name", "Crime_Year", "Crime_Month"])
    )
    
    top_crimes = (
        df_train.groupby("Area_Name")["Crime_Category"]
        .agg(lambda x: x.value_counts().index[0])
        .to_dict()
    )
    
    monthly_avg = (
        monthly_crime.groupby("Area_Name")["Crime_Count"]
        .mean()
        .to_dict()
    )
    
    return {
        "area_crime": area_crime,
        "monthly_crime": monthly_crime,
        "top_crimes": top_crimes,
        "monthly_avg": monthly_avg,
        "area_classes": list(area_encoder.classes_),
    }

def train_risk_regressor(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    n_estimators: int = 120,
) -> RandomForestRegressor:
    model = RandomForestRegressor(
        n_estimators=n_estimators,
        max_depth=20,
        min_samples_split=10,
        min_samples_leaf=4,
        random_state=42,
        n_jobs=-1,
    )
    print("Training Random Forest Regressor (risk score 0-100)...")
    model.fit(X_train, y_train)
    return model

def perform_model_selection(X_train: pd.DataFrame, y_train: pd.Series) -> tuple[str, dict]:
    """Compare RF, ExtraTrees, GradientBoosting, and XGBoost using TimeSeriesSplit CV."""
    print("\n--- Performing Model Comparison & Hyperparameter Search ---")
    
    # Sub-sample training data if too large to ensure CV completes quickly
    max_cv_samples = 40000
    if len(X_train) > max_cv_samples:
        print(f"Sub-sampling CV training data from {len(X_train):,} to {max_cv_samples:,} rows...")
        X_cv, _, y_cv, _ = train_test_split(
            X_train, y_train, train_size=max_cv_samples, random_state=42, stratify=y_train
        )
    else:
        X_cv, y_cv = X_train, y_train
        
    # Use TimeSeriesSplit for temporal data validation
    cv = TimeSeriesSplit(n_splits=3)
    
    models = {
        "RandomForest": (
            RandomForestClassifier(random_state=42, n_jobs=-1),
            {
                "n_estimators": [100, 150],
                "max_depth": [14, 20],
                "min_samples_split": [5, 10],
                "class_weight": ["balanced"],
            }
        ),
        "ExtraTrees": (
            ExtraTreesClassifier(random_state=42, n_jobs=-1),
            {
                "n_estimators": [100],
                "max_depth": [14, 20],
                "class_weight": ["balanced"],
            }
        ),
        "GradientBoosting": (
            GradientBoostingClassifier(random_state=42),
            {
                "n_estimators": [100],
                "max_depth": [6, 10],
                "learning_rate": [0.05, 0.1],
            }
        )
    }
    
    if XGB_AVAILABLE:
        models["XGBoost"] = (
            XGBClassifier(random_state=42, n_jobs=-1, eval_metric="logloss"),
            {
                "n_estimators": [100, 150],
                "max_depth": [6, 10],
                "learning_rate": [0.05, 0.1],
            }
        )
        
    best_models = {}
    best_scores = {}
    
    for name, (model, params) in models.items():
        print(f"Tuning {name}...")
        search = RandomizedSearchCV(
            model,
            param_distributions=params,
            n_iter=4,
            scoring="f1",
            cv=cv,
            random_state=42,
            n_jobs=-1,
        )
        t0 = time.time()
        search.fit(X_cv, y_cv)
        print(f"  Completed in {time.time() - t0:.1f}s | Best F1-Score: {search.best_score_:.4f}")
        best_models[name] = search.best_estimator_
        best_scores[name] = search.best_score_
        
    # Select best model based on F1 Score
    best_name = max(best_scores, key=best_scores.get)
    print(f"\nBest Model Selected: {best_name} with F1-Score: {best_scores[best_name]:.4f}")
    return best_name, best_models[best_name]

def train_classifier(best_name: str, best_estimator, X_train: pd.DataFrame, y_train: pd.Series):
    """Re-train the selected best model on the full training dataset using sklearn clone."""
    from sklearn.base import clone
    print(f"\nRe-training best classifier ({best_name}) on full training dataset...")
    model = clone(best_estimator)
    model.fit(X_train, y_train)
    return model

def train_regressor(X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestRegressor | XGBRegressor:
    """Train risk regressor (output 0-100 risk score)."""
    print("\nTraining Risk Score Regressor...")
    if XGB_AVAILABLE:
        model = XGBRegressor(n_estimators=100, max_depth=6, learning_rate=0.08, random_state=42, n_jobs=-1)
    else:
        model = RandomForestRegressor(n_estimators=120, max_depth=16, min_samples_split=10, random_state=42, n_jobs=-1)
    model.fit(X_train, y_train)
    return model

def evaluate_model(model, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    y_pred = model.predict(X_test)
    
    # Try to predict probability for ROC-AUC
    if hasattr(model, "predict_proba"):
        y_prob = model.predict_proba(X_test)[:, 1]
        auc = float(roc_auc_score(y_test, y_prob))
    else:
        auc = 0.5
        
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
        "auc_roc": auc,
    }
    print("\n=== Classifier Evaluation (Unbiased Test Set) ===")
    print(f"Accuracy:  {metrics['accuracy']:.4f}")
    print(f"Precision: {metrics['precision']:.4f}")
    print(f"Recall:    {metrics['recall']:.4f}")
    print(f"F1 Score:  {metrics['f1_score']:.4f}")
    print(f"ROC-AUC:   {metrics['auc_roc']:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred, target_names=["Not Likely", "Likely"]))
    return metrics

def save_artifacts(
    model,
    encoders: dict,
    aggregates: dict,
    metrics: dict,
    output_dir: Path,
    risk_model=None,
    risk_metrics: dict | None = None,
    version: str | None = None,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    
    classifier_fn = "crime_rf_model.joblib"
    regressor_fn = "crime_risk_rf_model.joblib"
    
    # Save main artifacts
    joblib.dump(model, output_dir / classifier_fn)
    if risk_model is not None:
        joblib.dump(risk_model, output_dir / regressor_fn)
    joblib.dump(encoders, output_dir / "label_encoders.joblib")
    joblib.dump(aggregates, output_dir / "aggregates.joblib")
    
    meta = {
        "feature_columns": FEATURE_COLUMNS,
        "has_risk_regressor": risk_model is not None,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "version": version or "v1",
    }
    if risk_metrics:
        meta["risk_regressor"] = risk_metrics
        
    # Save auxiliary aggregates as csv for dashboard compatibility
    aggregates["area_crime"].to_csv(output_dir / "area_crime.csv", index=False)
    aggregates["monthly_crime"].to_csv(output_dir / "monthly_crime.csv", index=False)
    
    with open(output_dir / "metrics.json", "w", encoding="utf-8") as f:
        json.dump({**metrics, **meta}, f, indent=2)
        
    print(f"\nArtifacts saved to: {output_dir}")
    
    # Save a versioned copy if version parameter is specified
    if version:
        version_dir = output_dir / "versions" / version
        version_dir.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, version_dir / classifier_fn)
        if risk_model is not None:
            joblib.dump(risk_model, version_dir / regressor_fn)
        joblib.dump(encoders, version_dir / "label_encoders.joblib")
        joblib.dump(aggregates, version_dir / "aggregates.joblib")
        with open(version_dir / "metrics.json", "w", encoding="utf-8") as f:
            json.dump({**metrics, **meta}, f, indent=2)
        print(f"Saved versioned artifacts to: {version_dir}")

def main() -> None:
    parser = argparse.ArgumentParser(description="Train crime prediction model safely")
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=ARTIFACTS_DIR)
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row cap for faster training (default: full dataset)",
    )
    parser.add_argument("--n-estimators", type=int, default=150)
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--version", type=str, default="v1")
    args = parser.parse_args()

    # 1. Load data
    df = load_and_clean(args.data, max_rows=args.max_rows)
    
    # 2. Extract temporal markers
    df["Hour"] = df["Incident_Time"].apply(parse_time_hour)
    df["Day_Of_Week"] = df["Incident_Date"].dt.dayofweek
    df["Month"] = df["Incident_Date"].dt.month.fillna(df["Crime_Month"]).astype(int)
    
    df["Crime_Type"] = df["Crime_Category"]
    df["Area_Location"] = df["Area_Name"]
    
    coords = df["Area_Name"].map(
        lambda area: AREA_COORDINATES.get(area, DEFAULT_COORDINATES)
    )
    df["Latitude"] = coords.apply(lambda c: c[0])
    df["Longitude"] = coords.apply(lambda c: c[1])

    # 3. Train/Test split BEFORE any transformations or aggregates (temporal validation)
    # Since this is time-series data, sort by Incident_Date to prevent look-ahead leakage
    df = df.sort_values("Incident_Date").reset_index(drop=True)
    test_split_idx = int(len(df) * (1.0 - args.test_size))
    
    df_train = df.iloc[:test_split_idx].copy()
    df_test = df.iloc[test_split_idx:].copy()
    
    print(f"Training split samples: {len(df_train):,} | Test split samples: {len(df_test):,}")

    # 4. Generate Target (Crime_Likely) safely on training set
    print("Generating labels safely...")
    density_map, density_threshold = build_density_mapping(df_train)
    
    y_train = compute_crime_likely_label(df_train, density_map, density_threshold)
    y_test = compute_crime_likely_label(df_test, density_map, density_threshold)
    
    df_train["Crime_Likely"] = y_train
    df_test["Crime_Likely"] = y_test

    # 5. Fit Encoders on Training Data only
    print("Fitting categorical encoders...")
    encoders = fit_label_encoders(df_train)
    
    df_train = transform_categories(df_train, encoders)
    df_test = transform_categories(df_test, encoders)

    # 6. Apply Feature Engineering safely
    print("Engineering features safely...")
    df_train, training_aggregates = apply_training_features(df_train)
    
    # Test set engineering using training aggregations (Zero Leakage!)
    df_test, _ = apply_training_features(
        df_test,
        area_freq_map=training_aggregates["area_freq_map"],
        reference_year=training_aggregates["reference_year"],
        historical_monthly_crime=training_aggregates["historical_monthly_crime"],
    )

    # Generate Regressor Target (Risk_Score_Target)
    y_risk_train = build_risk_target(df_train, y_train)
    y_risk_test = build_risk_target(df_test, y_test)
    
    df_train["Risk_Score_Target"] = y_risk_train
    df_test["Risk_Score_Target"] = y_risk_test

    # Extract X, y arrays
    X_train = df_train[FEATURE_COLUMNS]
    X_test = df_test[FEATURE_COLUMNS]

    # 7. Model Selection & Tuning (F1 optimized)
    best_name, best_estimator = perform_model_selection(X_train, y_train)
    
    # 8. Train the final classifier and regressor
    classifier_model = train_classifier(best_name, best_estimator, X_train, y_train)
    regressor_model = train_regressor(df_train[FEATURE_COLUMNS], y_risk_train)

    # 9. Evaluate
    metrics = evaluate_model(classifier_model, X_test, y_test)
    metrics["train_samples"] = int(len(X_train))
    metrics["test_samples"] = int(len(X_test))
    metrics["features"] = FEATURE_COLUMNS
    metrics["selected_model"] = best_name
    
    y_risk_pred = regressor_model.predict(X_test)
    risk_metrics = {
        "mae": float(mean_absolute_error(y_risk_test, y_risk_pred)),
        "r2": float(r2_score(y_risk_test, y_risk_pred)),
    }
    print(f"Risk Regressor MAE: {risk_metrics['mae']:.2f} | R2: {risk_metrics['r2']:.4f}")

    # 10. Save aggregates & artifacts
    chat_aggregates = build_aggregates(df_train, encoders["area"])
    chat_aggregates["area_freq_map"] = training_aggregates["area_freq_map"]
    chat_aggregates["reference_year"] = training_aggregates["reference_year"]
    chat_aggregates["monthly_crime"] = training_aggregates["historical_monthly_crime"]
    
    save_artifacts(
        model=classifier_model,
        encoders=encoders,
        aggregates=chat_aggregates,
        metrics=metrics,
        output_dir=args.output,
        risk_model=regressor_model,
        risk_metrics=risk_metrics,
        version=args.version,
    )

if __name__ == "__main__":
    main()
