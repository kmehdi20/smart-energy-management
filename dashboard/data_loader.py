"""
Shared data loading utilities for dashboard pages.

Loads from CSV files (always available) or database (when running).
"""

import pandas as pd
import streamlit as st
from pathlib import Path

# Project root (relative to dashboard/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent


@st.cache_data(ttl=60)
def load_synthetic_data(filename: str = "synthetic_365d.csv") -> pd.DataFrame:
    """Load the main synthetic dataset."""
    path = PROJECT_ROOT / "ml" / "data" / "raw" / filename
    if not path.exists():
        # Try 90d fallback
        path = PROJECT_ROOT / "ml" / "data" / "raw" / "synthetic_90d.csv"
    if not path.exists():
        st.error(f"No dataset found. Run the simulator first.")
        return pd.DataFrame()

    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


@st.cache_data(ttl=300)
def load_processed_data(prefix: str = "consumption") -> dict:
    """Load train/val/test splits."""
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
    """Load saved model and generate predictions on test set."""
    import joblib
    import numpy as np

    model_dir = PROJECT_ROOT / "ml" / "models"
    # Try xgboost first, then random_forest
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

            model = artifact["model"]
            preds = model.predict(X)
            preds = np.maximum(preds, 0)

            target_col = artifact["target"]
            actuals = test_df[target_col].values

            return {
                "model_name": model_name,
                "timestamps": test_df["timestamp"],
                "actuals": actuals,
                "predictions": preds,
                "target_col": target_col,
            }
    return None


@st.cache_data(ttl=300)
def load_alerts() -> pd.DataFrame:
    """Load anomaly detection alerts."""
    path = PROJECT_ROOT / "ml" / "anomaly_detection" / "plots" / "alerts.csv"
    if path.exists():
        df = pd.read_csv(path)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df
    return pd.DataFrame()


@st.cache_data(ttl=300)
def load_optimization_comparison() -> dict | None:
    """Run optimization comparison and return results."""
    from optimization.compare import compare_strategies
    import numpy as np

    df = load_synthetic_data()
    if df.empty:
        return None

    # Use 7 summer days
    df["month"] = df["timestamp"].dt.month
    summer = df[df["month"].isin([6, 7, 8])]
    if len(summer) < 7 * 96:
        subset = df.head(7 * 96)
    else:
        subset = summer.head(7 * 96)

    pv = subset["pv_power_w"].values
    load = subset["load_power_w"].values
    flex = subset.get("flexible_load_w", pd.Series(0, index=subset.index)).values
    base = np.maximum(load - flex, 150)

    results = compare_strategies(pv, load, base)
    results["timestamps"] = subset["timestamp"].values
    return results
