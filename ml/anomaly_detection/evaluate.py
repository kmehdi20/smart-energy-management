"""
Anomaly detection evaluation.

Compares statistical and Isolation Forest methods against
the ground-truth is_anomaly labels (injected during simulation).
"""

import logging

import numpy as np
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score, confusion_matrix

logger = logging.getLogger(__name__)


def evaluate_detector(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    method_name: str = "",
) -> dict:
    """
    Compute precision, recall, F1 for anomaly detection.

    Parameters
    ----------
    y_true : array-like of bool
        Ground truth (True = anomaly).
    y_pred : array-like of bool
        Predicted (True = anomaly).

    Returns
    -------
    dict with precision, recall, f1, true_positives, false_positives, etc.
    """
    y_true = np.asarray(y_true, dtype=bool)
    y_pred = np.asarray(y_pred, dtype=bool)

    if y_true.sum() == 0:
        logger.warning("No ground-truth anomalies — cannot compute meaningful metrics")
        return {"precision": 0, "recall": 0, "f1": 0}

    precision = precision_score(y_true, y_pred, zero_division=0)
    recall = recall_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)

    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[False, True]).ravel()

    metrics = {
        "method": method_name,
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "true_positives": int(tp),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_negatives": int(tn),
        "total_anomalies_true": int(y_true.sum()),
        "total_anomalies_pred": int(y_pred.sum()),
    }

    logger.info(
        f"{method_name}: P={precision:.3f}, R={recall:.3f}, F1={f1:.3f} "
        f"(TP={tp}, FP={fp}, FN={fn})"
    )

    return metrics


def compare_detectors(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare statistical and Isolation Forest detectors.

    Parameters
    ----------
    results_df : pd.DataFrame
        Must have columns: is_anomaly, stat_anomaly, if_anomaly

    Returns
    -------
    pd.DataFrame comparison table
    """
    y_true = results_df["is_anomaly"].values

    rows = []

    if "stat_anomaly" in results_df.columns:
        stat_metrics = evaluate_detector(y_true, results_df["stat_anomaly"].values,
                                         "Statistical")
        rows.append(stat_metrics)

    if "if_anomaly" in results_df.columns:
        if_metrics = evaluate_detector(y_true, results_df["if_anomaly"].values,
                                       "Isolation Forest")
        rows.append(if_metrics)

    comparison = pd.DataFrame(rows)

    print(f"\n{'=' * 70}")
    print("ANOMALY DETECTION COMPARISON")
    print(f"{'=' * 70}")
    print(comparison[["method", "precision", "recall", "f1",
                       "true_positives", "false_positives", "false_negatives"]].to_string(index=False))
    print(f"{'=' * 70}")

    return comparison


def generate_alerts(results_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate human-readable alert messages from detected anomalies.

    Returns
    -------
    pd.DataFrame with columns: timestamp, alert_type, severity, message
    """
    alerts = []

    # Use whichever detector flagged the anomaly
    anomaly_mask = pd.Series(False, index=results_df.index)
    if "stat_anomaly" in results_df.columns:
        anomaly_mask |= results_df["stat_anomaly"]
    if "if_anomaly" in results_df.columns:
        anomaly_mask |= results_df["if_anomaly"]

    anomaly_rows = results_df[anomaly_mask]

    for _, row in anomaly_rows.iterrows():
        ts = row["timestamp"]
        hour = pd.to_datetime(ts).hour
        load = row.get("load_power_w", 0)

        # Classify alert type
        if 0 <= hour <= 5:
            alert_type = "night_anomaly"
            severity = "warning"
            message = (f"Unusual consumption at {ts}: {load:.0f} W "
                       f"detected during nighttime hours.")
        elif load > 5000:
            alert_type = "high_consumption"
            severity = "critical"
            message = (f"Very high consumption at {ts}: {load:.0f} W "
                       f"exceeds expected range significantly.")
        else:
            alert_type = "elevated_consumption"
            severity = "info"
            message = (f"Elevated consumption at {ts}: {load:.0f} W "
                       f"above normal for this time of day.")

        # Check for PV anomalies
        pv = row.get("pv_power_w", 0)
        irr = row.get("irradiance_wm2", 0)
        if 9 <= hour <= 16 and irr > 300 and pv < 200:
            alert_type = "pv_production_drop"
            severity = "warning"
            message = (f"PV production drop at {ts}: {pv:.0f} W "
                       f"despite irradiance of {irr:.0f} W/m².")

        alerts.append({
            "timestamp": ts,
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
        })

    alerts_df = pd.DataFrame(alerts)
    logger.info(f"Generated {len(alerts_df)} alerts")

    return alerts_df
