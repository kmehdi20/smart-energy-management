"""
MILP-based Energy Management System (Strategy B — Optimized).

Uses Mixed Integer Linear Programming to find the optimal:
    - Battery charge/discharge schedule
    - Flexible load start times
    - Grid import profile

Objective: minimize total daily cost (grid + battery degradation + peak penalty).

Solver: PuLP with CBC (free, open-source).
"""

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pulp

logger = logging.getLogger(__name__)


@dataclass
class FlexibleLoad:
    """Definition of a shiftable load."""
    name: str
    power_w: float
    duration_steps: int          # number of time steps the load runs
    earliest_step: int           # earliest allowed start step
    latest_step: int             # latest allowed start step


@dataclass
class OptimizationParams:
    """All parameters for the MILP optimizer."""
    # Battery
    battery_capacity_wh: float = 5120
    soc_min: float = 0.10
    soc_max: float = 0.95
    max_charge_w: float = 2500
    max_discharge_w: float = 2500
    charge_eff: float = 0.95
    discharge_eff: float = 0.95
    initial_soc: float = 0.50

    # Cost
    tariff_per_kwh: float = 1.20        # MAD/kWh flat rate
    peak_tariff_per_kwh: float = 1.80   # MAD/kWh during peak hours
    peak_start_step: int = 72           # 18:00 at 15-min resolution
    peak_end_step: int = 92             # 23:00
    battery_degradation_cost: float = 0.15  # MAD per kWh cycled
    peak_demand_penalty: float = 0.001  # MAD per W of peak

    # Time
    dt_hours: float = 0.25
    n_steps: int = 96                   # 24 hours at 15-min

    # Flexible loads
    flexible_loads: list = field(default_factory=lambda: [
        FlexibleLoad("Water Heater", 2000, 6, 32, 76),   # 08:00–19:00, 1.5h
        FlexibleLoad("Washing Machine", 500, 6, 40, 76),  # 10:00–19:00, 1.5h
        FlexibleLoad("Water Pump", 750, 4, 24, 68),       # 06:00–17:00, 1h
    ])


def solve_milp(
    pv_forecast: np.ndarray,
    base_load_forecast: np.ndarray,
    params: OptimizationParams | None = None,
) -> dict:
    """
    Solve the energy management optimization problem.

    Parameters
    ----------
    pv_forecast : np.ndarray
        Forecasted PV power for each time step (W). Length = n_steps.
    base_load_forecast : np.ndarray
        Forecasted non-flexible load for each time step (W). Length = n_steps.
    params : OptimizationParams
        System parameters.

    Returns
    -------
    dict with keys:
        - status: solver status string
        - schedule: pd.DataFrame with optimal dispatch
        - total_cost: float (MAD)
        - grid_kwh: float
        - peak_demand_w: float
        - flexible_schedule: dict mapping load name → start step
    """
    if params is None:
        params = OptimizationParams()

    T = params.n_steps
    dt = params.dt_hours

    # Validate inputs
    assert len(pv_forecast) == T, f"PV forecast length {len(pv_forecast)} != {T}"
    assert len(base_load_forecast) == T, f"Load forecast length {len(base_load_forecast)} != {T}"

    # ── Create problem ────────────────────────────────────
    prob = pulp.LpProblem("EMS_Optimization", pulp.LpMinimize)

    # ── Decision variables ────────────────────────────────

    # Battery charging power (W) at each step
    P_ch = [pulp.LpVariable(f"P_ch_{t}", 0, params.max_charge_w) for t in range(T)]
    # Battery discharging power (W) at each step
    P_dis = [pulp.LpVariable(f"P_dis_{t}", 0, params.max_discharge_w) for t in range(T)]
    # Binary: 1 = charging, 0 = can discharge (prevents simultaneous)
    z = [pulp.LpVariable(f"z_{t}", cat="Binary") for t in range(T)]
    # Grid import power (W)
    P_grid = [pulp.LpVariable(f"P_grid_{t}", 0) for t in range(T)]
    # SOC at each step (fraction)
    SOC = [pulp.LpVariable(f"SOC_{t}", params.soc_min, params.soc_max) for t in range(T)]
    # Peak demand variable
    P_peak = pulp.LpVariable("P_peak", 0)
    # Slack for unserved load (penalty-based soft constraint)
    P_slack = [pulp.LpVariable(f"P_slack_{t}", 0) for t in range(T)]
    SLACK_PENALTY = 10.0  # MAD/kWh — high cost to discourage but allows feasibility
    # PV curtailment (spill surplus when battery full and no export)
    P_curtail = [pulp.LpVariable(f"P_curtail_{t}", 0) for t in range(T)]

    # Flexible load binary variables: x[j][s] = 1 if load j starts at step s
    flex_vars = {}
    for fl in params.flexible_loads:
        start_begin = fl.earliest_step
        start_end = min(fl.latest_step - fl.duration_steps + 1, T - fl.duration_steps + 1)
        if start_end <= start_begin:
            start_end = start_begin + 1  # guarantee at least one option
        possible_starts = range(start_begin, start_end)
        flex_vars[fl.name] = {
            s: pulp.LpVariable(f"flex_{fl.name}_{s}", cat="Binary")
            for s in possible_starts
        }

    # ── Tariff vector ─────────────────────────────────────
    tariff = np.full(T, params.tariff_per_kwh)
    tariff[params.peak_start_step:params.peak_end_step] = params.peak_tariff_per_kwh

    # ── Flexible load power at each step ──────────────────
    # P_flex[t] = sum of flexible loads active at step t
    P_flex = [0.0 for _ in range(T)]

    for fl in params.flexible_loads:
        starts = flex_vars[fl.name]
        for s, x_s in starts.items():
            for d in range(fl.duration_steps):
                step = s + d
                if step < T:
                    P_flex[step] += fl.power_w * x_s

        # Each flexible load starts at most once (≤1 prevents infeasibility on high-load days)
        prob += pulp.lpSum(starts.values()) <= 1, f"flex_once_{fl.name}"

    # ── Constraints ───────────────────────────────────────

    for t in range(T):
        total_load = base_load_forecast[t] + P_flex[t]

        # Energy balance: PV + Grid + Discharge + Slack = Load + Charge + Curtail
        prob += (
            pv_forecast[t] + P_grid[t] + P_dis[t] + P_slack[t] == total_load + P_ch[t] + P_curtail[t],
            f"balance_{t}",
        )

        # No simultaneous charge/discharge
        prob += P_ch[t] <= params.max_charge_w * z[t], f"ch_limit_{t}"
        prob += P_dis[t] <= params.max_discharge_w * (1 - z[t]), f"dis_limit_{t}"

        # SOC dynamics
        if t == 0:
            prob += (
                SOC[t] == params.initial_soc
                + (params.charge_eff * P_ch[t] * dt) / params.battery_capacity_wh
                - (P_dis[t] * dt) / (params.discharge_eff * params.battery_capacity_wh),
                f"soc_init",
            )
        else:
            prob += (
                SOC[t] == SOC[t - 1]
                + (params.charge_eff * P_ch[t] * dt) / params.battery_capacity_wh
                - (P_dis[t] * dt) / (params.discharge_eff * params.battery_capacity_wh),
                f"soc_{t}",
            )

        # Peak demand tracking
        prob += P_peak >= P_grid[t], f"peak_{t}"

    # ── Objective function ────────────────────────────────
    # Grid cost
    grid_cost = pulp.lpSum([
        tariff[t] * P_grid[t] * dt / 1000.0 for t in range(T)
    ])

    # Battery degradation cost
    deg_cost = pulp.lpSum([
        params.battery_degradation_cost * P_dis[t] * dt / 1000.0 for t in range(T)
    ])

    # Peak demand penalty
    peak_cost = params.peak_demand_penalty * P_peak

    # Slack cost (unserved load penalty)
    slack_cost = pulp.lpSum([
        SLACK_PENALTY * P_slack[t] * dt / 1000.0 for t in range(T)
    ])

    prob += grid_cost + deg_cost + peak_cost + slack_cost, "total_cost"

    # ── Solve ─────────────────────────────────────────────
    solver = pulp.PULP_CBC_CMD(msg=0, timeLimit=60)
    prob.solve(solver)

    status = pulp.LpStatus[prob.status]
    logger.info(f"MILP solver status: {status}")

    if status != "Optimal":
        logger.warning(f"Solver did not find optimal solution: {status}")
        return {"status": status, "schedule": None, "total_cost": None}

    # ── Extract results ───────────────────────────────────
    soc_vals = np.array([SOC[t].varValue for t in range(T)])
    ch_vals = np.array([P_ch[t].varValue for t in range(T)])
    dis_vals = np.array([P_dis[t].varValue for t in range(T)])
    grid_vals = np.array([P_grid[t].varValue for t in range(T)])
    bat_power = ch_vals - dis_vals

    # Compute flexible load power per step
    flex_power = np.zeros(T)
    flex_schedule = {}
    for fl in params.flexible_loads:
        starts = flex_vars[fl.name]
        for s, x_s in starts.items():
            if x_s.varValue is not None and x_s.varValue > 0.5:
                flex_schedule[fl.name] = {
                    "start_step": s,
                    "start_time": f"{s * 15 // 60:02d}:{s * 15 % 60:02d}",
                    "end_step": s + fl.duration_steps,
                    "power_w": fl.power_w,
                }
                for d in range(fl.duration_steps):
                    if s + d < T:
                        flex_power[s + d] += fl.power_w
                break

    total_load = base_load_forecast + flex_power
    cost_per_step = grid_vals * dt / 1000.0 * tariff

    schedule = pd.DataFrame({
        "step": range(T),
        "time": [f"{t * 15 // 60:02d}:{t * 15 % 60:02d}" for t in range(T)],
        "pv_forecast_w": np.round(pv_forecast, 1),
        "base_load_w": np.round(base_load_forecast, 1),
        "flex_load_w": np.round(flex_power, 1),
        "total_load_w": np.round(total_load, 1),
        "battery_power_w": np.round(bat_power, 1),
        "grid_power_w": np.round(grid_vals, 1),
        "soc_pct": np.round(soc_vals * 100, 2),
        "cost_mad": np.round(cost_per_step, 4),
    })

    total_cost = sum(cost_per_step)
    grid_kwh = sum(grid_vals * dt / 1000.0)
    peak_w = P_peak.varValue

    logger.info(f"Optimization result: cost={total_cost:.2f} MAD, "
                f"grid={grid_kwh:.1f} kWh, peak={peak_w:.0f} W")

    return {
        "status": status,
        "schedule": schedule,
        "total_cost": round(total_cost, 2),
        "grid_kwh": round(grid_kwh, 2),
        "peak_demand_w": round(peak_w, 1),
        "flexible_schedule": flex_schedule,
        "objective_value": pulp.value(prob.objective),
    }
