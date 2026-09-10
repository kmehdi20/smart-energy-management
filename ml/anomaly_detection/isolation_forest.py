"""
Isolation Forest anomaly detection.

Method: Train an Isolation Forest on normal consumption patterns,
then score new data. Points with low anomaly scores are flagged.

This is the ML-based method compared against the statistical baseline.
"""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

# Features used by Isolation Forest
IF_FEATURES = [
    "load_power_w",
    "hour",
    "day_of_week",
    "is_weekend",
    "temperature_c",
    "irradiance_wm2",
    "pv_power_w",
    "soc_pct",
]


def train_isolation_forest(
    train_df: pd.DataFrame,
    contamination: float = 0.02,
    model_dir: str = "ml/models",
) -> dict:
    """
    Train Isolation Forest on normal training data.

    Parameters
    ----------
    train_df : pd.DataFrame
        Training data (assumed mostly normal).
    contamination : float
        Expected fraction of anomalies in training data.
    model_dir : str
        Where to save the model.

    Returns
    -------
    dict with 'model', 'scaler', 'features'
    """
    # Add time features if not present
    df = train_df.copy()
    if "hour" not in df.columns:
        df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour
    if "day_of_week" not in df.columns:
        df["day_of_week"] = pd.to_datetime(df["timestamp"]).dt.dayofweek
    if "is_weekend" not in df.columns:
        df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

    available = [f for f in IF_FEATURES if f in df.columns]
    X = df[available].values

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Train
    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        max_samples="auto",
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_scaled)

    logger.info(f"Trained Isolation Forest: {len(available)} features, "
                f"contamination={contamination}")

    # Save
    Path(model_dir).mkdir(parents=True, exist_ok=True)
    artifact = {"model": model, "scaler": scaler, "features": available}
    model_path = Path(model_dir) / "anomaly_isolation_forest.joblib"
    joblib.dump(artifact, model_path)
    logger.info(f"Saved: {model_path}")

    return artifact


def detect_isolation_forest(
    df: pd.DataFrame,
    artifact: dict,
) -> pd.DataFrame:
    """
    Detect anomalies using a trained Isolation Forest.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset to scan.
    artifact : dict
        Output from train_isolation_forest().

    Returns
    -------
    pd.DataFrame
        Copy of df with added columns:
        - if_anomaly: boolean flag
        - if_score: anomaly score (lower = more anomalous)
    """
    model = artifact["model"]
    scaler = artifact["scaler"]
    features = artifact["features"]

    result = df.copy()
    if "hour" not in result.columns:
        result["hour"] = pd.to_datetime(result["timestamp"]).dt.hour
    if "day_of_week" not in result.columns:
        result["day_of_week"] = pd.to_datetime(result["timestamp"]).dt.dayofweek
    if "is_weekend" not in result.columns:
        result["is_weekend"] = (result["day_of_week"] >= 5).astype(int)

    X = result[features].values
    X_scaled = scaler.transform(X)

    # Predict: 1 = normal, -1 = anomaly
    labels = model.predict(X_scaled)
    scores = model.decision_function(X_scaled)

    result["if_anomaly"] = labels == -1
    result["if_score"] = scores

    n_anomalies = result["if_anomaly"].sum()
    logger.info(f"Isolation Forest detection: {n_anomalies} anomalies in {len(df)} rows")

    return result
