"""
Run the full preprocessing pipeline: clean → features → split → save.

Usage:
    python -m ml.preprocessing.run --csv ml/data/raw/synthetic_365d.csv
    python -m ml.preprocessing.run --csv ml/data/raw/synthetic_90d.csv --target pv
"""

import argparse
import logging

from .clean import clean_dataset
from .features import build_features, get_feature_columns
from .split import chronological_split, save_splits

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def run_pipeline(csv_path: str, target: str = "consumption", output_dir: str = "ml/data/processed"):
    """Execute the full preprocessing pipeline."""

    # Step 1 — Clean
    df = clean_dataset(csv_path)

    # Step 2 — Feature engineering
    df = build_features(df)

    # Step 3 — Get feature/target column definitions
    config = get_feature_columns(target)
    feature_cols = config["features"]
    target_col = config["target"]

    # Filter to only columns that exist (handles optional sensors)
    available = [c for c in feature_cols if c in df.columns]
    missing = [c for c in feature_cols if c not in df.columns]
    if missing:
        logger.warning(f"Missing feature columns (skipped): {missing}")

    logger.info(f"Target: {target_col}")
    logger.info(f"Features: {len(available)} / {len(feature_cols)}")

    # Step 4 — Chronological split
    train_df, val_df, test_df = chronological_split(
        df,
        train_frac=0.70,
        val_frac=0.15,
        test_frac=0.15,
        drop_na_features=True,
        feature_cols=available,
    )

    # Step 5 — Save
    save_splits(train_df, val_df, test_df, output_dir=output_dir, prefix=target)

    # Summary
    print("\n" + "=" * 60)
    print(f"PREPROCESSING COMPLETE — target: {target_col}")
    print("=" * 60)
    print(f"Features:     {len(available)}")
    print(f"Train set:    {len(train_df):,} rows")
    print(f"Val set:      {len(val_df):,} rows")
    print(f"Test set:     {len(test_df):,} rows")
    print(f"Train period: {train_df['timestamp'].iloc[0]} → {train_df['timestamp'].iloc[-1]}")
    print(f"Test period:  {test_df['timestamp'].iloc[0]} → {test_df['timestamp'].iloc[-1]}")

    # Feature stats
    print(f"\nTarget stats (train):")
    print(f"  mean:  {train_df[target_col].mean():.1f} W")
    print(f"  std:   {train_df[target_col].std():.1f} W")
    print(f"  min:   {train_df[target_col].min():.1f} W")
    print(f"  max:   {train_df[target_col].max():.1f} W")
    print("=" * 60)

    return train_df, val_df, test_df


def main():
    parser = argparse.ArgumentParser(description="Run preprocessing pipeline")
    parser.add_argument("--csv", required=True, help="Path to raw CSV")
    parser.add_argument(
        "--target", default="consumption", choices=["consumption", "pv"],
        help="Prediction target (default: consumption)"
    )
    parser.add_argument(
        "--output", default="ml/data/processed",
        help="Output directory for processed CSVs"
    )
    args = parser.parse_args()

    run_pipeline(args.csv, target=args.target, output_dir=args.output)


if __name__ == "__main__":
    main()
