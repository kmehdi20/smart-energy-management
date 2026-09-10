"""
Data cleaning pipeline.

Handles missing values, duplicates, outliers, invalid timestamps,
and sensor noise for the synthetic/real energy dataset.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def load_raw_dataset(csv_path: str) -> pd.DataFrame:
    """Load raw CSV and parse timestamps."""
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)
    logger.info(f"Loaded {len(df)} rows from {csv_path}")
    return df


def remove_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Remove duplicate timestamps, keeping the first occurrence."""
    before = len(df)
    df = df.drop_duplicates(subset=["timestamp"], keep="first").reset_index(drop=True)
    removed = before - len(df)
    if removed > 0:
        logger.info(f"Removed {removed} duplicate timestamps")
    return df


def handle_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill missing values using appropriate strategies:
    - Numeric columns: linear interpolation (max gap = 4 steps = 1 hour)
    - Remaining NaNs: forward fill then backward fill
    """
    numeric_cols = df.select_dtypes(include=[np.number]).columns

    # Count missing before
    missing_before = df[numeric_cols].isna().sum().sum()

    # Linear interpolation for short gaps
    df[numeric_cols] = df[numeric_cols].interpolate(
        method="linear", limit=4, limit_direction="both"
    )

    # Forward fill then backward fill for remaining
    df[numeric_cols] = df[numeric_cols].ffill().bfill()

    missing_after = df[numeric_cols].isna().sum().sum()
    if missing_before > 0:
        logger.info(f"Missing values: {missing_before} → {missing_after}")

    return df


def clip_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clip physically impossible values to valid ranges.
    These are hard engineering limits, not statistical thresholds.
    """
    clips = {
        "pv_power_w": (0, 6000),         # 4 kWp system, max ~5 kW with overshoot
        "load_power_w": (0, 20000),       # reasonable max for residential
        "grid_power_w": (0, 20000),
        "soc_pct": (0, 100),
        "irradiance_wm2": (0, 1400),      # max possible GHI
        "temperature_c": (-10, 55),        # Morocco realistic range
        "humidity_pct": (0, 100),
        "battery_power_w": (-3000, 3000),  # ±2500 W nominal
        "pv_voltage_v": (0, 100),
        "pv_current_a": (0, 60),
        "battery_voltage_v": (40, 58),
    }

    clipped_count = 0
    for col, (lo, hi) in clips.items():
        if col not in df.columns:
            continue
        mask = (df[col] < lo) | (df[col] > hi)
        n = mask.sum()
        if n > 0:
            df[col] = df[col].clip(lo, hi)
            clipped_count += n

    if clipped_count > 0:
        logger.info(f"Clipped {clipped_count} out-of-range values")

    return df


def validate_energy_balance(df: pd.DataFrame, tolerance_w: float = 500) -> pd.DataFrame:
    """
    Flag rows where energy balance residual exceeds tolerance.
    Does not remove them — adds a boolean column for downstream filtering.
    """
    if not all(c in df.columns for c in ["pv_power_w", "grid_power_w", "load_power_w", "battery_power_w"]):
        logger.warning("Cannot validate energy balance — missing columns")
        df["balance_valid"] = True
        return df

    bat_discharge = (-df["battery_power_w"]).clip(lower=0)
    bat_charge = df["battery_power_w"].clip(lower=0)
    curtailed = df.get("pv_curtailed_w", 0)

    supply = df["pv_power_w"] + df["grid_power_w"] + bat_discharge
    demand = df["load_power_w"] + bat_charge + curtailed
    residual = (supply - demand).abs()

    df["balance_valid"] = residual <= tolerance_w
    invalid = (~df["balance_valid"]).sum()
    if invalid > 0:
        logger.info(f"Energy balance violations (>{tolerance_w} W): {invalid} rows")

    return df


def clean_dataset(csv_path: str) -> pd.DataFrame:
    """
    Run the full cleaning pipeline.

    Returns a cleaned DataFrame ready for feature engineering.
    """
    logger.info("=" * 50)
    logger.info("CLEANING PIPELINE")
    logger.info("=" * 50)

    df = load_raw_dataset(csv_path)
    df = remove_duplicates(df)
    df = handle_missing_values(df)
    df = clip_outliers(df)
    df = validate_energy_balance(df)

    logger.info(f"Cleaned dataset: {len(df)} rows, {len(df.columns)} columns")
    return df
