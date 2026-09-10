"""
Feature engineering for energy consumption and PV forecasting.

Creates time-based, lag, rolling, and cross features from cleaned data.
All features use only past/present data — no future leakage.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Steps per hour at 15-min resolution
SPH = 4


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Extract calendar features from timestamp.

    These capture daily/weekly/seasonal consumption patterns.
    """
    ts = df["timestamp"]

    df["hour"] = ts.dt.hour
    df["minute"] = ts.dt.minute
    df["day_of_week"] = ts.dt.dayofweek          # 0=Monday, 6=Sunday
    df["day_of_year"] = ts.dt.dayofyear
    df["month"] = ts.dt.month
    df["is_weekend"] = (ts.dt.dayofweek >= 5).astype(int)

    # Cyclical encoding (helps ML models understand that hour 23 → 0 is close)
    df["hour_sin"] = np.sin(2 * np.pi * df["hour"] / 24)
    df["hour_cos"] = np.cos(2 * np.pi * df["hour"] / 24)
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

    logger.info("Added 12 time features")
    return df


def add_lag_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add lagged values of key variables.

    Lags are chosen to capture:
    - Previous time step (15 min ago)
    - Same hour yesterday (96 steps ago)
    - Same hour last week (672 steps ago)
    """
    lag_configs = {
        "load_power_w": [1, 2, 4, SPH * 24, SPH * 24 * 7],     # 15m, 30m, 1h, 24h, 7d
        "pv_power_w": [1, 4, SPH * 24],                          # 15m, 1h, 24h
        "grid_power_w": [1, SPH * 24],                            # 15m, 24h
        "soc_pct": [1, 4],                                        # 15m, 1h
        "temperature_c": [1, SPH * 24],                            # 15m, 24h
        "irradiance_wm2": [1, 4, SPH * 24],                       # 15m, 1h, 24h
    }

    count = 0
    for col, lags in lag_configs.items():
        if col not in df.columns:
            continue
        for lag in lags:
            lag_name = f"{col}_lag{lag}"
            df[lag_name] = df[col].shift(lag)
            count += 1

    logger.info(f"Added {count} lag features")
    return df


def add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add rolling statistics over different windows.

    Windows chosen:
    - 1 hour (4 steps): short-term trend
    - 4 hours (16 steps): medium-term trend
    - 24 hours (96 steps): daily pattern
    """
    roll_configs = {
        "load_power_w": [SPH, SPH * 4, SPH * 24],
        "pv_power_w": [SPH, SPH * 4],
        "temperature_c": [SPH * 4, SPH * 24],
        "irradiance_wm2": [SPH, SPH * 4],
    }

    count = 0
    for col, windows in roll_configs.items():
        if col not in df.columns:
            continue
        for w in windows:
            # Rolling mean (shift 1 to avoid including current step → no leakage)
            mean_name = f"{col}_rmean{w}"
            df[mean_name] = df[col].shift(1).rolling(window=w, min_periods=1).mean()
            count += 1

            # Rolling std (only for load — useful for anomaly context)
            if col == "load_power_w":
                std_name = f"{col}_rstd{w}"
                df[std_name] = df[col].shift(1).rolling(window=w, min_periods=1).std()
                count += 1

    logger.info(f"Added {count} rolling features")
    return df


def add_derived_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add computed features that combine multiple raw variables.
    """
    count = 0

    # Net power (positive = surplus PV, negative = deficit)
    if "pv_power_w" in df.columns and "load_power_w" in df.columns:
        df["net_power_w"] = df["pv_power_w"] - df["load_power_w"]
        count += 1

    # PV capacity factor (fraction of peak capacity)
    if "pv_power_w" in df.columns:
        pv_peak = 4000  # from config
        df["pv_capacity_factor"] = df["pv_power_w"] / pv_peak
        count += 1

    # Load intensity (relative to daily max — computed from lagged 24h max)
    if "load_power_w" in df.columns:
        df["load_24h_max"] = df["load_power_w"].shift(1).rolling(
            window=SPH * 24, min_periods=1
        ).max()
        df["load_intensity"] = np.where(
            df["load_24h_max"] > 0,
            df["load_power_w"] / df["load_24h_max"],
            0
        )
        count += 2

    # Temperature deviation from daily mean (captures AC usage trigger)
    if "temperature_c" in df.columns:
        df["temp_daily_mean"] = df["temperature_c"].shift(1).rolling(
            window=SPH * 24, min_periods=1
        ).mean()
        df["temp_deviation"] = df["temperature_c"] - df["temp_daily_mean"]
        count += 2

    logger.info(f"Added {count} derived features")
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Run the full feature engineering pipeline.

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned dataset with timestamp column.

    Returns
    -------
    pd.DataFrame
        Dataset with all features added. First rows may have NaNs
        from lag/rolling operations — these are dropped by the splitter.
    """
    logger.info("=" * 50)
    logger.info("FEATURE ENGINEERING")
    logger.info("=" * 50)

    df = df.copy()
    df = add_time_features(df)
    df = add_lag_features(df)
    df = add_rolling_features(df)
    df = add_derived_features(df)

    total_features = len(df.columns)
    logger.info(f"Feature engineering complete: {total_features} total columns")

    return df


def get_feature_columns(target: str = "consumption") -> dict:
    """
    Return the feature column lists for a given prediction target.

    Parameters
    ----------
    target : str
        'consumption' or 'pv'

    Returns
    -------
    dict with keys: 'features', 'target'
    """
    # Common time features
    time_feats = [
        "hour", "hour_sin", "hour_cos",
        "day_of_week", "dow_sin", "dow_cos",
        "month", "month_sin", "month_cos",
        "is_weekend",
    ]

    if target == "consumption":
        return {
            "target": "load_power_w",
            "features": time_feats + [
                # Lags
                "load_power_w_lag1", "load_power_w_lag2",
                "load_power_w_lag4", "load_power_w_lag96",
                "load_power_w_lag672",
                # Rolling
                "load_power_w_rmean4", "load_power_w_rmean16",
                "load_power_w_rmean96",
                "load_power_w_rstd4", "load_power_w_rstd96",
                # Weather
                "temperature_c", "temperature_c_lag96",
                "temperature_c_rmean96",
                "irradiance_wm2",
                # Derived
                "pv_power_w", "soc_pct",
                "load_intensity",
                "temp_deviation",
            ],
        }

    elif target == "pv":
        return {
            "target": "pv_power_w",
            "features": time_feats + [
                # Lags
                "pv_power_w_lag1", "pv_power_w_lag4",
                "pv_power_w_lag96",
                "irradiance_wm2", "irradiance_wm2_lag1",
                "irradiance_wm2_lag4", "irradiance_wm2_lag96",
                # Rolling
                "pv_power_w_rmean4", "pv_power_w_rmean16",
                "irradiance_wm2_rmean4", "irradiance_wm2_rmean16",
                # Weather
                "temperature_c", "temperature_c_lag96",
                # Derived
                "pv_capacity_factor",
                "temp_deviation",
            ],
        }

    else:
        raise ValueError(f"Unknown target: {target}. Use 'consumption' or 'pv'.")
