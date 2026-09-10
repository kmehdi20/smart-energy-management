"""
Performance comparison: Rule-Based EMS vs MILP-Optimized EMS.

Runs both strategies on the same day(s) of data and computes
energy, cost, and environmental metrics.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .rule_based import run_rule_based
from .milp_optimizer import solve_milp, OptimizationParams

logger = logging.getLogger(__name__)


def compare_strategies(
    pv_power: np.ndarray,
    total_load: np.ndarray,
    base_load: np.ndarray | None = None,
    tariff: float = 1.20,
    co2_factor: float = 0.65,
    dt_hours: float = 0.25,
) -> dict:
    """
    Run both EMS strategies and compare.

    Parameters
    ----------
    pv_power : np.ndarray
        PV generation (W), length must be multiple of 96.
    total_load : np.ndarray
        Total building load including flexible loads at default times (W).
    base_load : np.ndarray or None
        Non-flexible load only (W). If None, uses total_load.
    tariff : float
        Electricity tariff (MAD/kWh).
    co2_factor : float
        Grid CO₂ emissions factor (kg/kWh).
    dt_hours : float
        Time step in hours.

    Returns
    -------
    dict with 'baseline', 'optimized', 'comparison', 'daily_results'
    """
    n = len(pv_power)
    n_days = n // 96

    if base_load is None:
        base_load = total_load

    logger.info(f"Comparing strategies over {n_days} days ({n} steps)")

    # ── Strategy A: Rule-Based ────────────────────────────
    baseline = run_rule_based(
        pv_power, total_load, dt_hours=dt_hours, tariff_per_kwh=tariff,
    )

    # ── Strategy B: MILP (day by day) ─────────────────────
    opt_grid = np.zeros(n)
    opt_bat = np.zeros(n)
    opt_soc = np.zeros(n)
    opt_cost = np.zeros(n)
    opt_flex_schedules = []
    current_soc = 0.50

    for day in range(n_days):
        start = day * 96
        end = start + 96

        pv_day = pv_power[start:end]
        base_day = base_load[start:end]

        # Clamp SOC to feasible range before passing to solver
        safe_soc = max(0.12, min(0.93, current_soc))

        params = OptimizationParams(
            initial_soc=safe_soc,
            tariff_per_kwh=tariff,
        )

        result = solve_milp(pv_day, base_day, params)

        if result["status"] == "Optimal" and result["schedule"] is not None:
            sched = result["schedule"]
            opt_grid[start:end] = sched["grid_power_w"].values
            opt_bat[start:end] = sched["battery_power_w"].values
            opt_soc[start:end] = sched["soc_pct"].values / 100.0
            opt_cost[start:end] = sched["cost_mad"].values
            current_soc = sched["soc_pct"].iloc[-1] / 100.0
            opt_flex_schedules.append(result.get("flexible_schedule", {}))
        else:
            # Fallback to rule-based for this day
            logger.warning(f"Day {day}: MILP failed, using rule-based fallback")
            day_baseline = run_rule_based(
                pv_day, total_load[start:end],
                dt_hours=dt_hours, tariff_per_kwh=tariff,
                initial_soc=current_soc,
            )
            opt_grid[start:end] = day_baseline["grid_power_w"].values
            opt_bat[start:end] = day_baseline["battery_power_w"].values
            opt_soc[start:end] = day_baseline["soc_pct"].values / 100.0
            opt_cost[start:end] = day_baseline["cost_mad"].values
            current_soc = day_baseline["soc_pct"].iloc[-1] / 100.0

    # ── Compute metrics ───────────────────────────────────
    def compute_metrics(grid_w, pv_w, load_w, cost_arr, label):
        grid_kwh = (grid_w * dt_hours / 1000.0).sum()
        pv_kwh = (pv_w * dt_hours / 1000.0).sum()
        load_kwh = (load_w * dt_hours / 1000.0).sum()
        pv_used = min(pv_kwh, load_kwh - grid_kwh) if grid_kwh < load_kwh else 0
        self_consumption = (pv_used / pv_kwh * 100) if pv_kwh > 0 else 0
        self_sufficiency = ((load_kwh - grid_kwh) / load_kwh * 100) if load_kwh > 0 else 0
        total_cost = cost_arr.sum()
        co2 = grid_kwh * co2_factor
        peak = grid_w.max()

        return {
            "strategy": label,
            "grid_import_kwh": round(grid_kwh, 1),
            "pv_generation_kwh": round(pv_kwh, 1),
            "load_consumption_kwh": round(load_kwh, 1),
            "self_consumption_pct": round(self_consumption, 1),
            "self_sufficiency_pct": round(max(self_sufficiency, 0), 1),
            "total_cost_mad": round(total_cost, 2),
            "daily_avg_cost_mad": round(total_cost / max(n_days, 1), 2),
            "peak_grid_w": round(peak, 0),
            "co2_kg": round(co2, 1),
            "co2_daily_kg": round(co2 / max(n_days, 1), 2),
        }

    baseline_metrics = compute_metrics(
        baseline["grid_power_w"].values, pv_power, total_load,
        baseline["cost_mad"].values, "Rule-Based (Baseline)"
    )

    optimized_metrics = compute_metrics(
        opt_grid, pv_power, total_load, opt_cost, "MILP-Optimized"
    )

    # ── Improvement calculation ───────────────────────────
    def pct_improvement(baseline_val, optimized_val):
        if baseline_val == 0:
            return 0
        return round((baseline_val - optimized_val) / baseline_val * 100, 1)

    improvement = {
        "grid_reduction_pct": pct_improvement(
            baseline_metrics["grid_import_kwh"], optimized_metrics["grid_import_kwh"]
        ),
        "cost_reduction_pct": pct_improvement(
            baseline_metrics["total_cost_mad"], optimized_metrics["total_cost_mad"]
        ),
        "peak_reduction_pct": pct_improvement(
            baseline_metrics["peak_grid_w"], optimized_metrics["peak_grid_w"]
        ),
        "co2_reduction_pct": pct_improvement(
            baseline_metrics["co2_kg"], optimized_metrics["co2_kg"]
        ),
        "self_consumption_gain_pp": round(
            optimized_metrics["self_consumption_pct"] - baseline_metrics["self_consumption_pct"], 1
        ),
    }

    return {
        "baseline": baseline_metrics,
        "optimized": optimized_metrics,
        "improvement": improvement,
        "baseline_df": baseline,
        "optimized_grid": opt_grid,
        "optimized_soc": opt_soc * 100,
        "optimized_cost": opt_cost,
        "flexible_schedules": opt_flex_schedules,
    }


def print_comparison(results: dict):
    """Print a formatted comparison table."""
    b = results["baseline"]
    o = results["optimized"]
    imp = results["improvement"]

    print(f"\n{'=' * 70}")
    print("PERFORMANCE COMPARISON: Baseline vs Optimized")
    print(f"{'=' * 70}")
    print(f"{'Metric':<30s} {'Baseline':>12s} {'Optimized':>12s} {'Improvement':>12s}")
    print("-" * 70)
    print(f"{'Grid import (kWh)':<30s} {b['grid_import_kwh']:>12.1f} {o['grid_import_kwh']:>12.1f} {imp['grid_reduction_pct']:>11.1f}%")
    print(f"{'Total cost (MAD)':<30s} {b['total_cost_mad']:>12.2f} {o['total_cost_mad']:>12.2f} {imp['cost_reduction_pct']:>11.1f}%")
    print(f"{'Daily avg cost (MAD)':<30s} {b['daily_avg_cost_mad']:>12.2f} {o['daily_avg_cost_mad']:>12.2f}")
    print(f"{'Peak grid demand (W)':<30s} {b['peak_grid_w']:>12.0f} {o['peak_grid_w']:>12.0f} {imp['peak_reduction_pct']:>11.1f}%")
    print(f"{'Self-consumption (%)':<30s} {b['self_consumption_pct']:>12.1f} {o['self_consumption_pct']:>12.1f} {imp['self_consumption_gain_pp']:>+11.1f}pp")
    print(f"{'Self-sufficiency (%)':<30s} {b['self_sufficiency_pct']:>12.1f} {o['self_sufficiency_pct']:>12.1f}")
    print(f"{'CO₂ emissions (kg)':<30s} {b['co2_kg']:>12.1f} {o['co2_kg']:>12.1f} {imp['co2_reduction_pct']:>11.1f}%")
    print(f"{'CO₂ daily avg (kg)':<30s} {b['co2_daily_kg']:>12.2f} {o['co2_daily_kg']:>12.2f}")
    print(f"{'=' * 70}")


def plot_comparison(results: dict, pv_power: np.ndarray, load_power: np.ndarray,
                    save_dir: str = "optimization/plots"):
    """Generate comparison plots."""
    Path(save_dir).mkdir(parents=True, exist_ok=True)

    b = results["baseline"]
    o = results["optimized"]

    # ── Bar chart: key metrics ────────────────────────────
    metrics = ["grid_import_kwh", "total_cost_mad", "peak_grid_w", "co2_kg"]
    labels = ["Grid (kWh)", "Cost (MAD)", "Peak (W)", "CO₂ (kg)"]

    fig, axes = plt.subplots(1, 4, figsize=(16, 4))
    for i, (metric, label) in enumerate(zip(metrics, labels)):
        vals = [b[metric], o[metric]]
        colors = ["#e74c3c", "#2ecc71"]
        axes[i].bar(["Baseline", "Optimized"], vals, color=colors)
        axes[i].set_title(label)
        for j, v in enumerate(vals):
            axes[i].text(j, v + v * 0.02, f"{v:.1f}", ha="center", fontsize=9)
    plt.suptitle("Baseline vs Optimized EMS", fontsize=13)
    plt.tight_layout()
    plt.savefig(f"{save_dir}/comparison_bars.png", bbox_inches="tight", dpi=120)
    plt.close()

    # ── Day profile: first day ────────────────────────────
    day_steps = min(96, len(pv_power))
    hours = np.arange(day_steps) * 0.25

    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)

    # Power flows
    ax = axes[0]
    ax.plot(hours, pv_power[:day_steps], label="PV", color="#f39c12", linewidth=1.5)
    ax.plot(hours, load_power[:day_steps], label="Load", color="#3498db", linewidth=1.5)
    ax.plot(hours, results["baseline_df"]["grid_power_w"].values[:day_steps],
            label="Grid (Baseline)", color="#e74c3c", linewidth=1, linestyle="--")
    ax.plot(hours, results["optimized_grid"][:day_steps],
            label="Grid (Optimized)", color="#2ecc71", linewidth=1.5)
    ax.set_ylabel("Power (W)")
    ax.set_title("Day 1 — Power Flows")
    ax.legend(loc="upper right")
    ax.grid(True, alpha=0.3)

    # SOC
    ax = axes[1]
    ax.plot(hours, results["baseline_df"]["soc_pct"].values[:day_steps],
            label="SOC Baseline", color="#e74c3c", linestyle="--")
    ax.plot(hours, results["optimized_soc"][:day_steps],
            label="SOC Optimized", color="#2ecc71")
    ax.set_ylabel("SOC (%)")
    ax.set_title("Battery State of Charge")
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Cost
    ax = axes[2]
    ax.bar(hours, results["baseline_df"]["cost_mad"].values[:day_steps],
           width=0.2, alpha=0.5, color="#e74c3c", label="Cost Baseline")
    ax.bar(hours + 0.1, results["optimized_cost"][:day_steps],
           width=0.2, alpha=0.5, color="#2ecc71", label="Cost Optimized")
    ax.set_ylabel("Cost (MAD)")
    ax.set_xlabel("Hour")
    ax.set_title("Energy Cost per Interval")
    ax.legend()
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(f"{save_dir}/day1_profile.png", bbox_inches="tight", dpi=120)
    plt.close()

    logger.info(f"Comparison plots saved to {save_dir}/")
