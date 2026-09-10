"""
Performance Analysis — Phase 12.

Computes all metrics from the design document §20:
    - Total grid energy
    - PV self-consumption & self-sufficiency
    - Battery usage
    - Peak demand
    - Energy cost
    - CO₂ emissions
    - Forecasting accuracy
    - Anomaly detection results
    - Baseline vs optimized comparison with % improvement

Generates a full performance report as CSV + console output + plots.

Usage:
    python -m analysis.run --csv ml/data/raw/synthetic_365d.csv
"""

import argparse
import logging
import json
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PLOT_DIR = PROJECT_ROOT / "analysis" / "plots"
REPORT_DIR = PROJECT_ROOT / "analysis" / "reports"


# ── Energy System Metrics ─────────────────────────────────

def compute_energy_metrics(df: pd.DataFrame, dt_h: float = 0.25) -> dict:
    """Compute all energy metrics from the raw dataset."""
    pv_kwh = (df["pv_power_w"] * dt_h / 1000).sum()
    load_kwh = (df["load_power_w"] * dt_h / 1000).sum()
    grid_kwh = (df["grid_power_w"] * dt_h / 1000).sum()

    pv_to_load_kwh = (df["pv_to_load_w"] * dt_h / 1000).sum()
    pv_to_bat_kwh = (df["pv_to_battery_w"] * dt_h / 1000).sum()
    bat_to_load_kwh = (df["battery_to_load_w"] * dt_h / 1000).sum()
    curtailed_kwh = (df["pv_curtailed_w"] * dt_h / 1000).sum()

    bat_charge = df["battery_power_w"].clip(lower=0)
    bat_discharge = (-df["battery_power_w"]).clip(lower=0)
    bat_charge_kwh = (bat_charge * dt_h / 1000).sum()
    bat_discharge_kwh = (bat_discharge * dt_h / 1000).sum()

    n_days = len(df) / 96

    self_consumption = (pv_to_load_kwh + pv_to_bat_kwh) / pv_kwh * 100 if pv_kwh > 0 else 0
    self_sufficiency = (1 - grid_kwh / load_kwh) * 100 if load_kwh > 0 else 0

    return {
        "period_days": round(n_days, 1),
        "pv_generation_kwh": round(pv_kwh, 1),
        "load_consumption_kwh": round(load_kwh, 1),
        "grid_import_kwh": round(grid_kwh, 1),
        "pv_to_load_kwh": round(pv_to_load_kwh, 1),
        "pv_to_battery_kwh": round(pv_to_bat_kwh, 1),
        "battery_to_load_kwh": round(bat_to_load_kwh, 1),
        "pv_curtailed_kwh": round(curtailed_kwh, 1),
        "battery_charge_kwh": round(bat_charge_kwh, 1),
        "battery_discharge_kwh": round(bat_discharge_kwh, 1),
        "self_consumption_pct": round(self_consumption, 1),
        "self_sufficiency_pct": round(max(self_sufficiency, 0), 1),
        "peak_load_w": round(df["load_power_w"].max(), 0),
        "peak_pv_w": round(df["pv_power_w"].max(), 0),
        "peak_grid_w": round(df["grid_power_w"].max(), 0),
        "avg_soc_pct": round(df["soc_pct"].mean(), 1),
        "min_soc_pct": round(df["soc_pct"].min(), 1),
        "max_soc_pct": round(df["soc_pct"].max(), 1),
        "daily_pv_kwh": round(pv_kwh / n_days, 1),
        "daily_load_kwh": round(load_kwh / n_days, 1),
        "daily_grid_kwh": round(grid_kwh / n_days, 1),
    }


# ── Economic Metrics ─────────────────────────────────────

def compute_economic_metrics(
    grid_kwh: float,
    n_days: float,
    tariff: float = 1.20,
    co2_factor: float = 0.65,
) -> dict:
    """Compute cost and CO₂ metrics."""
    total_cost = grid_kwh * tariff
    daily_cost = total_cost / n_days if n_days > 0 else 0
    monthly_cost = daily_cost * 30
    annual_cost = daily_cost * 365
    co2_total = grid_kwh * co2_factor
    co2_daily = co2_total / n_days if n_days > 0 else 0

    return {
        "tariff_mad_kwh": tariff,
        "total_cost_mad": round(total_cost, 2),
        "daily_cost_mad": round(daily_cost, 2),
        "monthly_cost_mad": round(monthly_cost, 2),
        "annual_cost_mad": round(annual_cost, 2),
        "co2_factor_kg_kwh": co2_factor,
        "co2_total_kg": round(co2_total, 1),
        "co2_daily_kg": round(co2_daily, 2),
        "co2_annual_kg": round(co2_daily * 365, 1),
    }


# ── Forecasting Metrics ──────────────────────────────────

def compute_forecast_metrics() -> dict:
    """Load saved models and report their test metrics."""
    import joblib
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    results = {}
    model_dir = PROJECT_ROOT / "ml" / "models"
    data_dir = PROJECT_ROOT / "ml" / "data" / "processed"

    for target in ["consumption", "pv"]:
        for model_name in ["xgboost", "random_forest", "linear_regression"]:
            path = model_dir / f"{target}_{model_name}.joblib"
            test_path = data_dir / f"{target}_test.csv"

            if not path.exists() or not test_path.exists():
                continue

            artifact = joblib.load(path)
            test_df = pd.read_csv(test_path)
            features = [f for f in artifact["features"] if f in test_df.columns]
            target_col = artifact["target"]

            X = test_df[features].values
            y = test_df[target_col].values

            if artifact.get("scaler"):
                X = artifact["scaler"].transform(X)

            preds = np.maximum(artifact["model"].predict(X), 0)

            mae = mean_absolute_error(y, preds)
            rmse = np.sqrt(mean_squared_error(y, preds))
            r2 = r2_score(y, preds)
            mape = np.mean(np.abs(y - preds) / np.maximum(np.abs(y), 1)) * 100

            key = f"{target}_{model_name}"
            results[key] = {
                "target": target,
                "model": model_name,
                "mae_w": round(mae, 1),
                "rmse_w": round(rmse, 1),
                "mape_pct": round(mape, 1),
                "r2": round(r2, 4),
                "test_samples": len(y),
            }

            # Only keep best per target
            if target not in results or results.get(target, {}).get("rmse_w", 9999) > rmse:
                results[target] = results[key]

    return results


# ── Anomaly Detection Metrics ─────────────────────────────

def compute_anomaly_metrics() -> dict:
    """Load anomaly comparison results."""
    path = PROJECT_ROOT / "ml" / "anomaly_detection" / "plots" / "comparison.csv"
    if not path.exists():
        return {"status": "not_run"}

    comp = pd.read_csv(path)
    results = {}
    for _, row in comp.iterrows():
        results[row["method"].lower().replace(" ", "_")] = {
            "precision": row.get("precision", 0),
            "recall": row.get("recall", 0),
            "f1": row.get("f1", 0),
            "true_positives": int(row.get("true_positives", 0)),
            "false_positives": int(row.get("false_positives", 0)),
        }
    return results


# ── Optimization Comparison ───────────────────────────────

def compute_optimization_comparison(df: pd.DataFrame, days: int = 14) -> dict:
    """Run baseline vs optimized comparison."""
    from optimization.compare import compare_strategies

    df_m = df.copy()
    df_m["month"] = df_m["timestamp"].dt.month
    summer = df_m[df_m["month"].isin([6, 7, 8])]
    subset = summer.head(days * 96) if len(summer) >= days * 96 else df_m.head(days * 96)

    pv = subset["pv_power_w"].values
    load = subset["load_power_w"].values
    flex = subset.get("flexible_load_w", pd.Series(0, index=subset.index)).values
    base = np.maximum(load - flex, 150)

    results = compare_strategies(pv, load, base)
    return results


# ── Plot Generation ───────────────────────────────────────

def generate_plots(df: pd.DataFrame, opt_results: dict):
    """Generate all performance analysis plots."""
    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    dt = 0.25

    # 1. Monthly energy breakdown
    df_m = df.copy()
    df_m["month"] = df_m["timestamp"].dt.month
    monthly = df_m.groupby("month").agg(
        pv=("pv_power_w", lambda x: (x * dt / 1000).sum()),
        load=("load_power_w", lambda x: (x * dt / 1000).sum()),
        grid=("grid_power_w", lambda x: (x * dt / 1000).sum()),
    ).reset_index()

    fig, ax = plt.subplots(figsize=(10, 5))
    x = monthly["month"]
    w = 0.25
    ax.bar(x - w, monthly["pv"], w, label="PV Generation", color="#f39c12")
    ax.bar(x, monthly["load"], w, label="Load Consumption", color="#3498db")
    ax.bar(x + w, monthly["grid"], w, label="Grid Import", color="#e74c3c")
    ax.set_xlabel("Month")
    ax.set_ylabel("Energy (kWh)")
    ax.set_title("Monthly Energy Breakdown")
    ax.set_xticks(range(1, 13))
    ax.legend()
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "monthly_energy.png", dpi=150)
    plt.close()

    # 2. Daily self-consumption trend
    df_d = df.copy()
    df_d["date"] = df_d["timestamp"].dt.date
    daily = df_d.groupby("date").agg(
        pv=("pv_power_w", lambda x: (x * dt / 1000).sum()),
        pv_to_load=("pv_to_load_w", lambda x: (x * dt / 1000).sum()),
        load=("load_power_w", lambda x: (x * dt / 1000).sum()),
        grid=("grid_power_w", lambda x: (x * dt / 1000).sum()),
    ).reset_index()
    daily["self_cons"] = np.where(daily["pv"] > 0, daily["pv_to_load"] / daily["pv"] * 100, 0)
    daily["self_suff"] = np.where(daily["load"] > 0, (1 - daily["grid"] / daily["load"]) * 100, 0).clip(0)

    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(daily["date"], daily["self_cons"], label="Self-Consumption (%)", color="#f39c12", linewidth=0.8)
    ax.plot(daily["date"], daily["self_suff"], label="Self-Sufficiency (%)", color="#2ecc71", linewidth=0.8)
    ax.set_ylabel("%")
    ax.set_title("Daily Self-Consumption and Self-Sufficiency")
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "daily_self_consumption.png", dpi=150)
    plt.close()

    # 3. SOC distribution
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(df["soc_pct"], bins=50, color="#2ecc71", edgecolor="white", alpha=0.8)
    ax.axvline(x=10, color="red", linestyle="--", label="SOC min")
    ax.axvline(x=95, color="red", linestyle="--", label="SOC max")
    ax.set_xlabel("SOC (%)")
    ax.set_ylabel("Frequency")
    ax.set_title("Battery SOC Distribution")
    ax.legend()
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "soc_distribution.png", dpi=150)
    plt.close()

    # 4. Load duration curve
    load_sorted = np.sort(df["load_power_w"].values)[::-1]
    hours = np.arange(len(load_sorted)) * 0.25
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(hours, load_sorted, color="#3498db", linewidth=0.8)
    ax.set_xlabel("Hours")
    ax.set_ylabel("Load Power (W)")
    ax.set_title("Load Duration Curve")
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "load_duration_curve.png", dpi=150)
    plt.close()

    # 5. Optimization comparison bars
    b = opt_results["baseline"]
    o = opt_results["optimized"]

    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    for i, (metric, label) in enumerate([
        ("grid_import_kwh", "Grid Import (kWh)"),
        ("total_cost_mad", "Cost (MAD)"),
        ("co2_kg", "CO₂ (kg)"),
        ("self_consumption_pct", "Self-Consumption (%)"),
    ]):
        vals = [b[metric], o[metric]]
        colors = ["#e74c3c", "#2ecc71"]
        axes[i].bar(["Baseline", "Optimized"], vals, color=colors)
        axes[i].set_title(label)
        for j, v in enumerate(vals):
            axes[i].text(j, v + v * 0.02, f"{v:.1f}", ha="center", fontsize=9)
    plt.suptitle("Baseline vs Optimized EMS", fontsize=13, y=1.02)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "optimization_comparison.png", dpi=150, bbox_inches="tight")
    plt.close()

    # 6. Hourly average profiles
    df_h = df.copy()
    df_h["hour"] = df_h["timestamp"].dt.hour
    hourly = df_h.groupby("hour")[["pv_power_w", "load_power_w", "grid_power_w"]].mean()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(hourly.index, hourly["pv_power_w"], label="PV (avg)", color="#f39c12", linewidth=2)
    ax.plot(hourly.index, hourly["load_power_w"], label="Load (avg)", color="#3498db", linewidth=2)
    ax.plot(hourly.index, hourly["grid_power_w"], label="Grid (avg)", color="#e74c3c", linewidth=2)
    ax.fill_between(hourly.index, hourly["pv_power_w"], alpha=0.15, color="#f39c12")
    ax.set_xlabel("Hour of Day")
    ax.set_ylabel("Average Power (W)")
    ax.set_title("Average Hourly Power Profiles")
    ax.set_xticks(range(0, 24))
    ax.legend()
    ax.grid(alpha=0.3)
    plt.tight_layout()
    plt.savefig(PLOT_DIR / "hourly_profiles.png", dpi=150)
    plt.close()

    logger.info(f"Saved 6 plots to {PLOT_DIR}/")


# ── Report Generation ─────────────────────────────────────

def print_report(energy: dict, econ: dict, forecast: dict, anomaly: dict,
                 opt_results: dict):
    """Print the full performance report to console."""
    b = opt_results["baseline"]
    o = opt_results["optimized"]
    imp = opt_results["improvement"]

    print("\n" + "=" * 72)
    print("   PERFORMANCE ANALYSIS REPORT")
    print("   AI-Based Smart Energy Management System")
    print("=" * 72)

    print(f"\n{'─' * 72}")
    print("1. ENERGY SYSTEM METRICS")
    print(f"{'─' * 72}")
    print(f"  Period:                    {energy['period_days']:.0f} days")
    print(f"  PV Generation (total):     {energy['pv_generation_kwh']:.1f} kWh ({energy['daily_pv_kwh']:.1f} kWh/day)")
    print(f"  Load Consumption (total):  {energy['load_consumption_kwh']:.1f} kWh ({energy['daily_load_kwh']:.1f} kWh/day)")
    print(f"  Grid Import (total):       {energy['grid_import_kwh']:.1f} kWh ({energy['daily_grid_kwh']:.1f} kWh/day)")
    print(f"  PV Self-Consumption:       {energy['self_consumption_pct']:.1f}%")
    print(f"  Self-Sufficiency:          {energy['self_sufficiency_pct']:.1f}%")
    print(f"  Peak Load:                 {energy['peak_load_w']:.0f} W")
    print(f"  Peak PV:                   {energy['peak_pv_w']:.0f} W")
    print(f"  Peak Grid:                 {energy['peak_grid_w']:.0f} W")

    print(f"\n{'─' * 72}")
    print("2. BATTERY PERFORMANCE")
    print(f"{'─' * 72}")
    print(f"  Total Charged:             {energy['battery_charge_kwh']:.1f} kWh")
    print(f"  Total Discharged:          {energy['battery_discharge_kwh']:.1f} kWh")
    print(f"  Round-trip Efficiency:     {energy['battery_discharge_kwh'] / max(energy['battery_charge_kwh'], 1) * 100:.1f}%")
    print(f"  Average SOC:               {energy['avg_soc_pct']:.1f}%")
    print(f"  SOC Range:                 {energy['min_soc_pct']:.1f}% — {energy['max_soc_pct']:.1f}%")
    cycles = energy['battery_discharge_kwh'] / 5.12  # approx full cycles
    print(f"  Approx. Full Cycles:       {cycles:.0f}")

    print(f"\n{'─' * 72}")
    print("3. ECONOMIC ANALYSIS")
    print(f"{'─' * 72}")
    print(f"  Tariff:                    {econ['tariff_mad_kwh']:.2f} MAD/kWh")
    print(f"  Total Cost:                {econ['total_cost_mad']:.2f} MAD")
    print(f"  Daily Average:             {econ['daily_cost_mad']:.2f} MAD")
    print(f"  Monthly Estimate:          {econ['monthly_cost_mad']:.2f} MAD")
    print(f"  Annual Estimate:           {econ['annual_cost_mad']:.2f} MAD")

    print(f"\n{'─' * 72}")
    print("4. ENVIRONMENTAL ANALYSIS")
    print(f"{'─' * 72}")
    print(f"  CO₂ Factor:                {econ['co2_factor_kg_kwh']:.2f} kg/kWh (Morocco grid)")
    print(f"  Total CO₂:                 {econ['co2_total_kg']:.1f} kg")
    print(f"  Daily CO₂:                 {econ['co2_daily_kg']:.2f} kg")
    print(f"  Annual CO₂ Estimate:       {econ['co2_annual_kg']:.1f} kg")

    print(f"\n{'─' * 72}")
    print("5. ML FORECASTING PERFORMANCE")
    print(f"{'─' * 72}")
    for key, metrics in forecast.items():
        if isinstance(metrics, dict) and "mae_w" in metrics:
            print(f"  [{metrics['target']}] {metrics['model']}:")
            print(f"    MAE={metrics['mae_w']:.1f} W, RMSE={metrics['rmse_w']:.1f} W, "
                  f"MAPE={metrics['mape_pct']:.1f}%, R²={metrics['r2']:.4f} "
                  f"(n={metrics['test_samples']})")

    print(f"\n{'─' * 72}")
    print("6. ANOMALY DETECTION")
    print(f"{'─' * 72}")
    for method, metrics in anomaly.items():
        if isinstance(metrics, dict) and "f1" in metrics:
            print(f"  {method}: P={metrics['precision']:.3f}, R={metrics['recall']:.3f}, "
                  f"F1={metrics['f1']:.3f} (TP={metrics['true_positives']}, FP={metrics['false_positives']})")

    print(f"\n{'─' * 72}")
    print("7. OPTIMIZATION COMPARISON (Baseline vs Intelligent EMS)")
    print(f"{'─' * 72}")
    print(f"  {'Metric':<30s} {'Baseline':>12s} {'Optimized':>12s} {'Improvement':>12s}")
    print(f"  {'-' * 66}")
    print(f"  {'Grid Import (kWh)':<30s} {b['grid_import_kwh']:>12.1f} {o['grid_import_kwh']:>12.1f} {imp['grid_reduction_pct']:>11.1f}%")
    print(f"  {'Total Cost (MAD)':<30s} {b['total_cost_mad']:>12.2f} {o['total_cost_mad']:>12.2f} {imp['cost_reduction_pct']:>11.1f}%")
    print(f"  {'Peak Grid (W)':<30s} {b['peak_grid_w']:>12.0f} {o['peak_grid_w']:>12.0f} {imp['peak_reduction_pct']:>11.1f}%")
    print(f"  {'Self-Consumption (%)':<30s} {b['self_consumption_pct']:>12.1f} {o['self_consumption_pct']:>12.1f} {imp['self_consumption_gain_pp']:>+11.1f}pp")
    print(f"  {'CO₂ (kg)':<30s} {b['co2_kg']:>12.1f} {o['co2_kg']:>12.1f} {imp['co2_reduction_pct']:>11.1f}%")

    print(f"\n{'=' * 72}")
    print("   All results from synthetic simulation data (seed=42).")
    print("   Tariff and CO₂ factor are estimates — verify from official sources.")
    print(f"{'=' * 72}\n")


def save_report(energy: dict, econ: dict, forecast: dict, anomaly: dict,
                opt_results: dict):
    """Save report data as JSON for reuse."""
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    report = {
        "energy": energy,
        "economic": econ,
        "forecasting": forecast,
        "anomaly_detection": anomaly,
        "optimization": {
            "baseline": opt_results["baseline"],
            "optimized": opt_results["optimized"],
            "improvement": opt_results["improvement"],
        },
    }

    path = REPORT_DIR / "performance_report.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"Report saved to {path}")

    # Also save as CSV summary
    rows = []
    for section, data in report.items():
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, dict):
                    for k2, v2 in v.items():
                        rows.append({"section": section, "metric": f"{k}.{k2}", "value": v2})
                else:
                    rows.append({"section": section, "metric": k, "value": v})

    csv_path = REPORT_DIR / "performance_summary.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    logger.info(f"CSV summary saved to {csv_path}")


# ── Main ──────────────────────────────────────────────────

def run_analysis(csv_path: str):
    """Execute the full performance analysis."""
    logger.info("=" * 60)
    logger.info("PERFORMANCE ANALYSIS — Phase 12")
    logger.info("=" * 60)

    # Load data
    df = pd.read_csv(csv_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    logger.info(f"Loaded {len(df)} rows from {csv_path}")

    # 1. Energy metrics
    energy = compute_energy_metrics(df)

    # 2. Economic metrics
    econ = compute_economic_metrics(
        grid_kwh=energy["grid_import_kwh"],
        n_days=energy["period_days"],
    )

    # 3. Forecasting metrics
    forecast = compute_forecast_metrics()

    # 4. Anomaly detection metrics
    anomaly = compute_anomaly_metrics()

    # 5. Optimization comparison
    logger.info("Running optimization comparison (14 summer days)...")
    opt_results = compute_optimization_comparison(df, days=14)

    # 6. Generate plots
    logger.info("Generating plots...")
    generate_plots(df, opt_results)

    # 7. Print and save report
    print_report(energy, econ, forecast, anomaly, opt_results)
    save_report(energy, econ, forecast, anomaly, opt_results)

    logger.info("Performance analysis complete.")


def main():
    parser = argparse.ArgumentParser(description="Run performance analysis")
    parser.add_argument("--csv", required=True, help="Path to synthetic CSV")
    args = parser.parse_args()
    run_analysis(args.csv)


if __name__ == "__main__":
    main()
