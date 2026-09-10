"""
Run the full forecasting pipeline.

Usage:
    python -m ml.forecasting.run --csv ml/data/raw/synthetic_365d.csv --target consumption
    python -m ml.forecasting.run --csv ml/data/raw/synthetic_365d.csv --target pv
"""

import argparse
import logging
from pathlib import Path

import pandas as pd

from ..preprocessing import clean_dataset, build_features, get_feature_columns, chronological_split
from .train import train_models
from .evaluate import compare_models, evaluate_on_test
from .plots import (
    plot_actual_vs_predicted, plot_scatter,
    plot_model_comparison, plot_feature_importance,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_forecasting(csv_path: str, target: str = "consumption"):
    """Execute the full forecasting pipeline."""

    plot_dir = f"ml/forecasting/plots/{target}"
    model_dir = "ml/models"

    # ── Step 1: Preprocess ────────────────────────────────
    logger.info("=" * 60)
    logger.info(f"FORECASTING PIPELINE — Target: {target}")
    logger.info("=" * 60)

    df = clean_dataset(csv_path)
    df = build_features(df)

    config = get_feature_columns(target)
    feature_cols = config["features"]
    target_col = config["target"]

    available = [c for c in feature_cols if c in df.columns]

    # ── Step 2: Split ─────────────────────────────────────
    train_df, val_df, test_df = chronological_split(
        df, train_frac=0.70, val_frac=0.15, test_frac=0.15,
        drop_na_features=True, feature_cols=available,
    )

    # ── Step 3: Train ─────────────────────────────────────
    results = train_models(
        train_df, val_df,
        feature_cols=available,
        target_col=target_col,
        model_dir=model_dir,
        prefix=target,
    )

    # ── Step 4: Evaluate on validation set ────────────────
    y_val = val_df[target_col].values
    comparison = compare_models(results, y_val, target_name=target_col)

    # ── Step 5: Evaluate best model on TEST set ───────────
    best_name = comparison.iloc[0]["model"]
    if best_name != "naive_baseline":
        best_model_path = Path(model_dir) / f"{target}_{best_name}.joblib"
        logger.info(f"\nEvaluating best model ({best_name}) on TEST set:")
        test_result = evaluate_on_test(str(best_model_path), test_df, target_col)

        print(f"\n{'=' * 60}")
        print(f"TEST SET RESULTS — {best_name}")
        print(f"{'=' * 60}")
        for k, v in test_result["metrics"].items():
            print(f"  {k.upper():>6s}: {v:.2f}")
        print(f"{'=' * 60}")

        y_test_pred = test_result["predictions"]
        y_test_actual = test_result["actuals"]
    else:
        # If naive is best, still show test metrics
        from .train import naive_baseline
        y_test_pred = naive_baseline(train_df, test_df, target_col)
        y_test_actual = test_df[target_col].values
        from .evaluate import evaluate_model
        test_metrics = evaluate_model(y_test_actual, y_test_pred)
        print(f"\nTEST SET (naive baseline): RMSE={test_metrics['rmse']:.1f} W")

    # ── Step 6: Generate plots ────────────────────────────
    logger.info("Generating plots...")

    # Actual vs predicted — validation set (best model)
    best_val_preds = results[best_name]["predictions"]
    plot_actual_vs_predicted(
        val_df["timestamp"], y_val, best_val_preds,
        title=f"{target.title()} Forecast — Validation (last 7 days)",
        save_path=f"{plot_dir}/actual_vs_predicted_val.png",
    )

    # Actual vs predicted — test set
    plot_actual_vs_predicted(
        test_df["timestamp"], y_test_actual, y_test_pred,
        title=f"{target.title()} Forecast — Test Set (last 7 days)",
        save_path=f"{plot_dir}/actual_vs_predicted_test.png",
    )

    # Scatter plot — test set
    plot_scatter(
        y_test_actual, y_test_pred,
        title=f"{target.title()} — Predicted vs Actual (Test)",
        save_path=f"{plot_dir}/scatter_test.png",
    )

    # Model comparison
    plot_model_comparison(
        comparison,
        metric="RMSE (W)",
        save_path=f"{plot_dir}/model_comparison_rmse.png",
    )
    plot_model_comparison(
        comparison,
        metric="R²",
        save_path=f"{plot_dir}/model_comparison_r2.png",
    )

    # Feature importance (best tree-based model)
    if best_name in ("random_forest", "xgboost"):
        plot_feature_importance(
            results[best_name]["model"],
            available,
            title=f"{target.title()} — Feature Importance ({best_name})",
            save_path=f"{plot_dir}/feature_importance.png",
        )

    # Also plot for all tree models
    for name in ["random_forest", "xgboost"]:
        if name in results and results[name]["model"] is not None:
            plot_feature_importance(
                results[name]["model"],
                available,
                title=f"{target.title()} — Feature Importance ({name})",
                save_path=f"{plot_dir}/feature_importance_{name}.png",
            )

    logger.info(f"All plots saved to {plot_dir}/")
    logger.info("Forecasting pipeline complete.")

    return results, comparison


def main():
    parser = argparse.ArgumentParser(description="Run ML forecasting pipeline")
    parser.add_argument("--csv", required=True, help="Path to raw CSV")
    parser.add_argument(
        "--target", default="consumption", choices=["consumption", "pv"],
        help="Prediction target"
    )
    args = parser.parse_args()

    run_forecasting(args.csv, target=args.target)


if __name__ == "__main__":
    main()
