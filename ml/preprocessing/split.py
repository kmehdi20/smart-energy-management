"""
Chronological train/validation/test splitting.

CRITICAL: Time-series data must NOT be randomly shuffled.
The split preserves temporal order to prevent data leakage.

Split ratios (default):
    Train:      70% (first portion)
    Validation: 15% (middle portion — for hyperparameter tuning)
    Test:       15% (final portion — for reporting metrics)
"""

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def chronological_split(
    df: pd.DataFrame,
    train_frac: float = 0.70,
    val_frac: float = 0.15,
    test_frac: float = 0.15,
    drop_na_features: bool = True,
    feature_cols: list[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Split a time-ordered DataFrame into train/validation/test sets.

    Parameters
    ----------
    df : pd.DataFrame
        Must be sorted by timestamp.
    train_frac, val_frac, test_frac : float
        Split proportions (must sum to 1.0).
    drop_na_features : bool
        If True, drop rows where any feature column is NaN
        (typically the first ~672 rows due to lag features).
    feature_cols : list[str] or None
        If provided, only check these columns for NaN when dropping.

    Returns
    -------
    (train_df, val_df, test_df)
    """
    assert abs(train_frac + val_frac + test_frac - 1.0) < 1e-6, \
        f"Fractions must sum to 1.0, got {train_frac + val_frac + test_frac}"

    # Drop rows with NaN in feature columns (from lag/rolling operations)
    if drop_na_features and feature_cols:
        before = len(df)
        df = df.dropna(subset=feature_cols).reset_index(drop=True)
        dropped = before - len(df)
        if dropped > 0:
            logger.info(f"Dropped {dropped} rows with NaN features (lag warmup)")

    n = len(df)
    train_end = int(n * train_frac)
    val_end = int(n * (train_frac + val_frac))

    train_df = df.iloc[:train_end].copy()
    val_df = df.iloc[train_end:val_end].copy()
    test_df = df.iloc[val_end:].copy()

    logger.info(
        f"Split: train={len(train_df)} ({train_frac:.0%}), "
        f"val={len(val_df)} ({val_frac:.0%}), "
        f"test={len(test_df)} ({test_frac:.0%})"
    )
    logger.info(
        f"  Train: {train_df['timestamp'].iloc[0]} → {train_df['timestamp'].iloc[-1]}"
    )
    logger.info(
        f"  Val:   {val_df['timestamp'].iloc[0]} → {val_df['timestamp'].iloc[-1]}"
    )
    logger.info(
        f"  Test:  {test_df['timestamp'].iloc[0]} → {test_df['timestamp'].iloc[-1]}"
    )

    return train_df, val_df, test_df


def save_splits(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
    output_dir: str = "ml/data/processed",
    prefix: str = "",
):
    """Save splits to CSV files."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    p = f"{prefix}_" if prefix else ""
    train_path = out / f"{p}train.csv"
    val_path = out / f"{p}val.csv"
    test_path = out / f"{p}test.csv"

    train_df.to_csv(train_path, index=False)
    val_df.to_csv(val_path, index=False)
    test_df.to_csv(test_path, index=False)

    logger.info(f"Saved: {train_path}, {val_path}, {test_path}")
