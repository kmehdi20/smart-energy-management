"""
Run the full optimization comparison pipeline.

Usage:
    python -m optimization.run --csv ml/data/raw/synthetic_365d.csv --days 7
"""

import argparse
import logging

import pandas as pd
import numpy as np

from .compare import compare_strategies, print_comparison, plot_comparison

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_optimization(csv_path: str, days: int = 7):
    """Run the optimization comparison pipeline."""

    logger.info("=" * 60)
    logger.info("OPTIMIZATION COMPARISON PIPELINE")
    logger.info("=" * 60)

    # Load data
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)

    # Take the requested number of days (from a sunny period for best demo)
    # Find a summer period for clearer results
    df["month"] = df["timestamp"].dt.month
    summer = df[df["month"].isin([6, 7, 8])]

    if len(summer) >= days * 96:
        subset = summer.head(days * 96)
        logger.info(f"Using {days} summer days for comparison")
    else:
        subset = df.head(days * 96)
        logger.info(f"Using first {days} days for comparison")

    n = len(subset)
    if n < 96:
        logger.error("Not enough data (need at least 96 steps = 1 day)")
        return

    pv_power = subset["pv_power_w"].values
    total_load = subset["load_power_w"].values

    # Base load = total minus flexible loads (these get rescheduled by MILP)
    flex_col = "flexible_load_w" if "flexible_load_w" in subset.columns else None
    if flex_col:
        base_load = (subset["load_power_w"].values - subset[flex_col].values)
        base_load = np.maximum(base_load, 150)  # never below standby
    else:
        base_load = total_load.copy()

    # Run comparison
    results = compare_strategies(
        pv_power=pv_power,
        total_load=total_load,
        base_load=base_load,
        tariff=1.20,
        co2_factor=0.65,
    )

    # Print results
    print_comparison(results)

    # Print flexible load schedules (first day)
    if results["flexible_schedules"]:
        sched = results["flexible_schedules"][0]
        print(f"\nFlexible Load Schedule (Day 1):")
        for name, info in sched.items():
            print(f"  {name}: start at {info['start_time']}, "
                  f"power={info['power_w']} W")

    # Generate plots
    plot_comparison(results, pv_power, total_load)

    logger.info("Optimization pipeline complete.")
    return results


def main():
    parser = argparse.ArgumentParser(description="Run EMS optimization comparison")
    parser.add_argument("--csv", required=True, help="Path to synthetic CSV")
    parser.add_argument("--days", type=int, default=7, help="Number of days (default: 7)")
    args = parser.parse_args()

    run_optimization(args.csv, days=args.days)


if __name__ == "__main__":
    main()
