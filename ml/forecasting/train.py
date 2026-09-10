"""
Model training for energy consumption and PV forecasting.

Trains multiple models, evaluates on validation set, selects the best,
and saves it for inference.

Models:
    1. Naive baseline (same hour previous week)
    2. Linear Regression
    3. Random Forest
    4. XGBoost
"""

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


def _try_import_xgboost():
    """Import XGBoost if available."""
    try:
        from xgboost import XGBRegressor
        return XGBRegressor
    except ImportError:
        logger.warning("XGBoost not installed — skipping. Install with: pip install xgboost")
        return None


def naive_baseline(train_df: pd.DataFrame, test_df: pd.DataFrame,
                   target_col: str) -> np.ndarray:
    """
    Naive forecast: predict using the same hour, same day-of-week
    from the most recent matching occurrence in train.

    Falls back to the hourly mean from training data.
    """
    # Build lookup: (hour, day_of_week) → mean target value from train
    train_df = train_df.copy()
    train_df["_hour"] = pd.to_datetime(train_df["timestamp"]).dt.hour
    train_df["_dow"] = pd.to_datetime(train_df["timestamp"]).dt.dayofweek

    lookup = train_df.groupby(["_hour", "_dow"])[target_col].mean().to_dict()
    hourly_mean = train_df.groupby("_hour")[target_col].mean().to_dict()
    global_mean = train_df[target_col].mean()

    test_df = test_df.copy()
    test_df["_hour"] = pd.to_datetime(test_df["timestamp"]).dt.hour
    test_df["_dow"] = pd.to_datetime(test_df["timestamp"]).dt.dayofweek

    predictions = []
    for _, row in test_df.iterrows():
        key = (row["_hour"], row["_dow"])
        pred = lookup.get(key, hourly_mean.get(row["_hour"], global_mean))
        predictions.append(pred)

    return np.array(predictions)


def train_models(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    feature_cols: list[str],
    target_col: str,
    model_dir: str = "ml/models",
    prefix: str = "consumption",
) -> dict:
    """
    Train all models and return results.

    Parameters
    ----------
    train_df, val_df : pd.DataFrame
        Preprocessed datasets with features and target.
    feature_cols : list[str]
        Feature column names.
    target_col : str
        Target column name.
    model_dir : str
        Directory to save trained models.
    prefix : str
        Filename prefix ('consumption' or 'pv').

    Returns
    -------
    dict: {model_name: {'model': fitted_model, 'predictions': np.array, 'scaler': scaler}}
    """
    Path(model_dir).mkdir(parents=True, exist_ok=True)

    # Filter to available features
    available = [c for c in feature_cols if c in train_df.columns]

    X_train = train_df[available].values
    y_train = train_df[target_col].values
    X_val = val_df[available].values
    y_val = val_df[target_col].values

    # Scale features (important for Linear Regression)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)

    results = {}

    # ── 1. Naive Baseline ─────────────────────────────────
    logger.info("Training: Naive Baseline")
    naive_preds = naive_baseline(train_df, val_df, target_col)
    results["naive_baseline"] = {
        "model": None,
        "predictions": naive_preds,
        "scaler": None,
    }

    # ── 2. Linear Regression ──────────────────────────────
    logger.info("Training: Linear Regression")
    lr = LinearRegression()
    lr.fit(X_train_scaled, y_train)
    lr_preds = lr.predict(X_val_scaled)
    lr_preds = np.maximum(lr_preds, 0)  # power can't be negative
    results["linear_regression"] = {
        "model": lr,
        "predictions": lr_preds,
        "scaler": scaler,
    }

    # ── 3. Random Forest ──────────────────────────────────
    logger.info("Training: Random Forest")
    rf = RandomForestRegressor(
        n_estimators=200,
        max_depth=15,
        min_samples_split=10,
        min_samples_leaf=5,
        n_jobs=-1,
        random_state=42,
    )
    rf.fit(X_train, y_train)  # RF doesn't need scaling
    rf_preds = rf.predict(X_val)
    rf_preds = np.maximum(rf_preds, 0)
    results["random_forest"] = {
        "model": rf,
        "predictions": rf_preds,
        "scaler": None,
    }

    # ── 4. XGBoost ────────────────────────────────────────
    XGBRegressor = _try_import_xgboost()
    if XGBRegressor is not None:
        logger.info("Training: XGBoost")
        xgb = XGBRegressor(
            n_estimators=300,
            max_depth=8,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            n_jobs=-1,
            verbosity=0,
        )
        xgb.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )
        xgb_preds = xgb.predict(X_val)
        xgb_preds = np.maximum(xgb_preds, 0)
        results["xgboost"] = {
            "model": xgb,
            "predictions": xgb_preds,
            "scaler": None,
        }

    # ── Save all models ───────────────────────────────────
    for name, data in results.items():
        if data["model"] is not None:
            model_path = Path(model_dir) / f"{prefix}_{name}.joblib"
            joblib.dump({
                "model": data["model"],
                "scaler": data["scaler"],
                "features": available,
                "target": target_col,
            }, model_path)
            logger.info(f"Saved: {model_path}")

    # Save feature list
    feature_path = Path(model_dir) / f"{prefix}_features.joblib"
    joblib.dump(available, feature_path)

    return results
