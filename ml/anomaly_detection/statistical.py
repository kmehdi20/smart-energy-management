"""
Statistical anomaly detection.

Method: For each hour-of-day, compute rolling mean and std of consumption
from historical data, then flag any value exceeding mean ± k × std.

This is the simple, interpretable baseline method.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def build_hourly_thresholds(
    train_df: pd.DataFrame,
    target_col: str = "load_power_w",
    k: float = 2.5,
) -> pd.DataFrame:
    """
    Build per-hour upper/lower thresholds from training data.

    Parameters
    ----------
    train_df : pd.DataFrame
        Training dataset with timestamp and target column.
    target_col : str
        Column to model.
    k : float
        Number of standard deviations for the threshold.

    Returns
    -------
    pd.DataFrame
        24 rows (one per hour) with columns: hour, mean, std, upper, lower
    """
    df = train_df.copy()
    df["hour"] = pd.to_datetime(df["timestamp"]).dt.hour

    stats = df.groupby("hour")[target_col].agg(["mean", "std"]).reset_index()
    stats["upper"] = stats["mean"] + k * stats["std"]
    stats["lower"] = (stats["mean"] - k * stats["std"]).clip(lower=0)
    stats["k"] = k

    logger.info(f"Built hourly thresholds (k={k}) from {len(train_df)} training samples")
    return stats


def detect_statistical(
    df: pd.DataFrame,
    thresholds: pd.DataFrame,
    target_col: str = "load_power_w",
) -> pd.DataFrame:
    """
    Detect anomalies using per-hour statistical thresholds.

    Parameters
    ----------
    df : pd.DataFrame
        Dataset to scan (validation or test).
    thresholds : pd.DataFrame
        Output from build_hourly_thresholds().

    Returns
    -------
    pd.DataFrame
        Copy of df with added columns:
        - stat_upper, stat_lower: thresholds for that hour
        - stat_anomaly: boolean flag
        - stat_deviation: how far above/below threshold (W)
    """
    result = df.copy()
    result["hour"] = pd.to_datetime(result["timestamp"]).dt.hour

    # Merge thresholds
    result = result.merge(
        thresholds[["hour", "upper", "lower"]],
        on="hour",
        how="left",
        suffixes=("", "_thresh"),
    )
    result.rename(columns={"upper": "stat_upper", "lower": "stat_lower"}, inplace=True)

    # Flag anomalies
    above = result[target_col] > result["stat_upper"]
    below = result[target_col] < result["stat_lower"]
    result["stat_anomaly"] = above | below

    # Deviation (positive = above threshold, negative = below)
    result["stat_deviation"] = np.where(
        above,
        result[target_col] - result["stat_upper"],
        np.where(below, result[target_col] - result["stat_lower"], 0),
    )

    n_anomalies = result["stat_anomaly"].sum()
    logger.info(f"Statistical detection: {n_anomalies} anomalies in {len(df)} rows")

    return result
