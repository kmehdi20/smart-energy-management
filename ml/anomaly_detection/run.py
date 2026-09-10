"""
Run the full anomaly detection pipeline.

Usage:
    python -m ml.anomaly_detection.run --csv ml/data/raw/synthetic_365d.csv
"""

import argparse
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np

from ..preprocessing import clean_dataset, build_features
from .statistical import build_hourly_thresholds, detect_statistical
from .isolation_forest import train_isolation_forest, detect_isolation_forest
from .evaluate import compare_detectors, generate_alerts

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def plot_anomalies(
    df: pd.DataFrame,
    anomaly_col: str,
    target_col: str = "load_power_w",
    title: str = "Anomaly Detection",
    save_path: str | None = None,
    days: int = 14,
):
    """Plot consumption with anomalies highlighted."""
    ts = pd.to_datetime(df["timestamp"])
    cutoff = ts.max() - pd.Timedelta(days=days)
    mask = ts >= cutoff
    sub = df[mask]
    ts_sub = ts[mask]

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(ts_sub, sub[target_col], linewidth=0.8, alpha=0.7, label="Load")

    # Highlight anomalies
    anom_mask = sub[anomaly_col].values.astype(bool)
    ax.scatter(
        ts_sub[anom_mask], sub[target_col].values[anom_mask],
        color="red", s=15, zorder=5, label="Detected anomaly"
    )

    # Highlight ground truth if available
    if "is_anomaly" in sub.columns:
        gt_mask = sub["is_anomaly"].values.astype(bool)
        ax.scatter(
            ts_sub[gt_mask], sub[target_col].values[gt_mask],
            color="none", edgecolors="green", s=30, zorder=4,
            linewidths=1.2, label="True anomaly"
        )

    ax.set_title(title)
    ax.set_ylabel("Power (W)")
    ax.legend(loc="upper right")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    plt.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, bbox_inches="tight", dpi=120)
        logger.info(f"Saved plot: {save_path}")
    plt.close()


def run_anomaly_detection(csv_path: str):
    """Execute the full anomaly detection pipeline."""
    plot_dir = "ml/anomaly_detection/plots"

    logger.info("=" * 60)
    logger.info("ANOMALY DETECTION PIPELINE")
    logger.info("=" * 60)

    # ── Load and preprocess ───────────────────────────────
    df = clean_dataset(csv_path)
    df = build_features(df)

    # Split: use first 70% as training (normal behavior), rest for detection
    n = len(df)
    train_end = int(n * 0.70)
    train_df = df.iloc[:train_end].copy()
    detect_df = df.iloc[train_end:].copy()

    logger.info(f"Train (normal): {len(train_df)} rows")
    logger.info(f"Detect (scan):  {len(detect_df)} rows")

    # ── Method 1: Statistical ─────────────────────────────
    logger.info("\n--- Statistical Method ---")
    thresholds = build_hourly_thresholds(train_df, target_col="load_power_w", k=2.5)
    detect_df = detect_statistical(detect_df, thresholds, target_col="load_power_w")

    # ── Method 2: Isolation Forest ────────────────────────
    logger.info("\n--- Isolation Forest Method ---")
    artifact = train_isolation_forest(train_df, contamination=0.02)
    detect_df = detect_isolation_forest(detect_df, artifact)

    # ── Compare methods ───────────────────────────────────
    if "is_anomaly" in detect_df.columns:
        comparison = compare_detectors(detect_df)

        # Save comparison
        comparison.to_csv(f"{plot_dir}/comparison.csv", index=False)
    else:
        logger.warning("No ground-truth labels — skipping precision/recall evaluation")

    # ── Generate alerts ───────────────────────────────────
    alerts = generate_alerts(detect_df)
    alerts_path = f"{plot_dir}/alerts.csv"
    Path(alerts_path).parent.mkdir(parents=True, exist_ok=True)
    alerts.to_csv(alerts_path, index=False)

    # Print sample alerts
    print(f"\n{'=' * 70}")
    print("SAMPLE ALERTS (first 10)")
    print(f"{'=' * 70}")
    for _, alert in alerts.head(10).iterrows():
        print(f"  [{alert['severity']:>8s}] {alert['alert_type']:>25s} | {alert['message'][:80]}")
    print(f"  ... ({len(alerts)} total alerts)")
    print(f"{'=' * 70}")

    # ── Plots ─────────────────────────────────────────────
    plot_anomalies(
        detect_df, "stat_anomaly",
        title="Statistical Anomaly Detection (last 14 days)",
        save_path=f"{plot_dir}/statistical_anomalies.png",
    )
    plot_anomalies(
        detect_df, "if_anomaly",
        title="Isolation Forest Anomaly Detection (last 14 days)",
        save_path=f"{plot_dir}/isolation_forest_anomalies.png",
    )

    # Threshold visualization
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(thresholds["hour"], thresholds["mean"], color="#3498db", alpha=0.7, label="Mean")
    ax.fill_between(
        thresholds["hour"], thresholds["lower"], thresholds["upper"],
        alpha=0.2, color="red", label=f"±{thresholds['k'].iloc[0]}σ threshold"
    )
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Load Power (W)")
    ax.set_title("Hourly Consumption Thresholds (from training data)")
    ax.legend()
    ax.set_xticks(range(0, 24))
    plt.tight_layout()
    thresh_path = f"{plot_dir}/hourly_thresholds.png"
    plt.savefig(thresh_path, bbox_inches="tight", dpi=120)
    logger.info(f"Saved plot: {thresh_path}")
    plt.close()

    logger.info("Anomaly detection pipeline complete.")


def main():
    parser = argparse.ArgumentParser(description="Run anomaly detection pipeline")
    parser.add_argument("--csv", required=True, help="Path to raw CSV")
    args = parser.parse_args()

    run_anomaly_detection(args.csv)


if __name__ == "__main__":
    main()
