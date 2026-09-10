"""
Visualization for forecasting results.

Generates:
    - Actual vs predicted time series
    - Scatter plot (predicted vs actual)
    - Model comparison bar chart
    - Feature importance (for tree-based models)
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

logger = logging.getLogger(__name__)

# Style
plt.rcParams.update({
    "figure.figsize": (14, 5),
    "figure.dpi": 120,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "font.size": 10,
})


def plot_actual_vs_predicted(
    timestamps: pd.Series,
    y_true: np.ndarray,
    y_pred: np.ndarray,
    title: str = "Actual vs Predicted",
    ylabel: str = "Power (W)",
    save_path: str | None = None,
    days: int = 7,
):
    """
    Plot actual vs predicted for the last N days of the dataset.

    Parameters
    ----------
    timestamps : pd.Series
        Datetime values.
    y_true, y_pred : np.ndarray
        Actual and predicted values.
    days : int
        Number of days to show (last N days for readability).
    save_path : str
        If provided, saves the figure.
    """
    ts = pd.to_datetime(timestamps)

    # Show last N days for readability
    cutoff = ts.max() - pd.Timedelta(days=days)
    mask = ts >= cutoff

    fig, ax = plt.subplots(figsize=(14, 5))
    ax.plot(ts[mask], y_true[mask], label="Actual", linewidth=1, alpha=0.8)
    ax.plot(ts[mask], y_pred[mask], label="Predicted", linewidth=1, alpha=0.8,
            linestyle="--")
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.set_xlabel("Time")
    ax.legend()
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
    ax.tick_params(axis="x", rotation=30)
    plt.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, bbox_inches="tight")
        logger.info(f"Saved plot: {save_path}")
    plt.close()


def plot_scatter(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    title: str = "Predicted vs Actual",
    save_path: str | None = None,
):
    """Scatter plot of predicted vs actual with perfect-prediction line."""
    fig, ax = plt.subplots(figsize=(6, 6))

    ax.scatter(y_true, y_pred, alpha=0.1, s=5, color="steelblue")

    # Perfect prediction line
    lims = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]
    ax.plot(lims, lims, "r--", linewidth=1, label="Perfect prediction")

    ax.set_xlabel("Actual (W)")
    ax.set_ylabel("Predicted (W)")
    ax.set_title(title)
    ax.legend()
    ax.set_aspect("equal")
    plt.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, bbox_inches="tight")
        logger.info(f"Saved plot: {save_path}")
    plt.close()


def plot_model_comparison(
    comparison_df: pd.DataFrame,
    metric: str = "RMSE (W)",
    save_path: str | None = None,
):
    """Bar chart comparing models on a given metric."""
    fig, ax = plt.subplots(figsize=(8, 5))

    colors = ["#2ecc71" if i == 0 else "#3498db"
              for i in range(len(comparison_df))]

    ax.barh(comparison_df["model"], comparison_df[metric], color=colors)
    ax.set_xlabel(metric)
    ax.set_title(f"Model Comparison — {metric}")
    ax.invert_yaxis()

    # Add value labels
    for i, v in enumerate(comparison_df[metric]):
        ax.text(v + 1, i, f"{v:.1f}", va="center", fontsize=9)

    plt.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, bbox_inches="tight")
        logger.info(f"Saved plot: {save_path}")
    plt.close()


def plot_feature_importance(
    model,
    feature_names: list[str],
    top_n: int = 15,
    title: str = "Feature Importance",
    save_path: str | None = None,
):
    """
    Plot feature importance for tree-based models.
    Works with RandomForest and XGBoost.
    """
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    else:
        logger.warning("Model does not have feature_importances_")
        return

    # Sort and take top N
    indices = np.argsort(importances)[::-1][:top_n]
    top_features = [feature_names[i] for i in indices]
    top_importances = importances[indices]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(range(top_n), top_importances[::-1], color="#3498db")
    ax.set_yticks(range(top_n))
    ax.set_yticklabels(top_features[::-1])
    ax.set_xlabel("Importance")
    ax.set_title(title)
    plt.tight_layout()

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(save_path, bbox_inches="tight")
        logger.info(f"Saved plot: {save_path}")
    plt.close()
