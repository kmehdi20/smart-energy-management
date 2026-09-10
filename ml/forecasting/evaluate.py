"""
Model evaluation metrics for forecasting.

Computes MAE, RMSE, MAPE, R² and produces a comparison table.
"""

import logging

import numpy as np
import pandas as pd
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

logger = logging.getLogger(__name__)


def mean_absolute_percentage_error(y_true: np.ndarray, y_pred: np.ndarray,
                                    epsilon: float = 1.0) -> float:
    """
    MAPE with epsilon floor to avoid division by zero.

    Parameters
    ----------
    y_true, y_pred : np.ndarray
    epsilon : float
        Minimum denominator value (default 1.0 W).
    """
    denom = np.maximum(np.abs(y_true), epsilon)
    return float(np.mean(np.abs(y_true - y_pred) / denom) * 100)


def evaluate_model(y_true: np.ndarray, y_pred: np.ndarray) -> dict:
    """
    Compute all evaluation metrics.

    Returns
    -------
    dict with keys: mae, rmse, mape, r2
    """
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "mape": mean_absolute_percentage_error(y_true, y_pred),
        "r2": float(r2_score(y_true, y_pred)),
    }


def compare_models(
    results: dict,
    y_true: np.ndarray,
    target_name: str = "load_power_w",
) -> pd.DataFrame:
    """
    Evaluate all models and produce a comparison table.

    Parameters
    ----------
    results : dict
        Output from train_models(): {name: {'predictions': array, ...}}
    y_true : np.ndarray
        Actual values from validation/test set.
    target_name : str
        Name of the target variable (for display).

    Returns
    -------
    pd.DataFrame
        Comparison table sorted by RMSE (lower is better).
    """
    rows = []
    for name, data in results.items():
        preds = data["predictions"]
        metrics = evaluate_model(y_true, preds)
        rows.append({
            "model": name,
            "MAE (W)": round(metrics["mae"], 1),
            "RMSE (W)": round(metrics["rmse"], 1),
            "MAPE (%)": round(metrics["mape"], 1),
            "R²": round(metrics["r2"], 4),
        })

    comparison = pd.DataFrame(rows).sort_values("RMSE (W)").reset_index(drop=True)

    print(f"\n{'=' * 70}")
    print(f"MODEL COMPARISON — Target: {target_name}")
    print(f"{'=' * 70}")
    print(comparison.to_string(index=False))
    print(f"{'=' * 70}")

    best = comparison.iloc[0]
    print(f"\nBest model: {best['model']} (RMSE = {best['RMSE (W)']:.1f} W, "
          f"R² = {best['R²']:.4f})")

    return comparison


def evaluate_on_test(
    model_path: str,
    test_df: pd.DataFrame,
    target_col: str,
) -> dict:
    """
    Load a saved model and evaluate on test set.

    Returns metrics dict and predictions array.
    """
    import joblib

    artifact = joblib.load(model_path)
    model = artifact["model"]
    scaler = artifact.get("scaler")
    features = artifact["features"]

    X_test = test_df[features].values
    y_test = test_df[target_col].values

    if scaler is not None:
        X_test = scaler.transform(X_test)

    y_pred = model.predict(X_test)
    y_pred = np.maximum(y_pred, 0)

    metrics = evaluate_model(y_test, y_pred)
    logger.info(f"Test evaluation: MAE={metrics['mae']:.1f}, "
                f"RMSE={metrics['rmse']:.1f}, R²={metrics['r2']:.4f}")

    return {"metrics": metrics, "predictions": y_pred, "actuals": y_test}
