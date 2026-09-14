"""
Shared data loading utilities for dashboard pages.
"""

import pandas as pd
import streamlit as st
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@st.cache_data(ttl=60)
def load_synthetic_data(filename: str = "synthetic_365d.csv") -> pd.DataFrame:
    path = PROJECT_ROOT / "ml" / "data" / "raw" / filename
    if not path.exists():
        path = PROJECT_ROOT / "ml" / "data" / "raw" / "synthetic_90d.csv"
    if not path.exists():
        st.error("No dataset found. Run the simulator first.")
        return pd.DataFrame()
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


@st.cache_data(ttl=300)
def load_processed_data(prefix: str = "consumption") -> dict:
    base = PROJECT_ROOT / "ml" / "data" / "processed"
    result = {}
    for split in ["train", "val", "test"]:
        path = base / f"{prefix}_{split}.csv"
        if path.exists():
            df = pd.read_csv(path)
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            result[split] = df
    return result


@st.cache_data(ttl=300)
def load_predictions(target: str = "consumption") -> dict | None:
    import joblib
    import numpy as np

    model_dir = PROJECT_ROOT / "ml" / "models"
    for model_name in ["xgboost", "random_forest", "linear_regression"]:
        path = model_dir / f"{target}_{model_name}.joblib"
        if path.exists():
            artifact = joblib.load(path)
            splits = load_processed_data(target)
            if "test" not in splits:
                return None
            test_df = splits["test"]
            features = artifact["features"]
            available = [f for f in features if f in test_df.columns]
            X = test_df[available].values
            if artifact.get("scaler"):
                X = artifact["scaler"].transform(X)
            preds = np.maximum(artifact["model"].predict(X), 0)
            return {
                "model_name": model_name,
                "timestamps": test_df["timestamp"],
                "actuals": test_df[artifact["target"]].values,
                "predictions": preds,
                "target_col": artifact["target"],
            }
    return None


@st.cache_data(ttl=300)
def load_alerts() -> pd.DataFrame:
    path = PROJECT_ROOT / "ml" / "anomaly_detection" / "plots" / "alerts.csv"
    if path.exists():
        df = pd.read_csv(path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df
    return pd.DataFrame()
