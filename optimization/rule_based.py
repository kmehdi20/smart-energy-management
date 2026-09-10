"""
Rule-based Energy Management System (Strategy A — Baseline).

Simple reactive rules with no forecasting or optimization:
    - PV surplus → charge battery
    - PV deficit → discharge battery
    - Remaining deficit → grid import
    - Flexible loads run at their default fixed times

This serves as the baseline for comparison with the MILP optimizer.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def run_rule_based(
    pv_power: np.ndarray,
    load_power: np.ndarray,
    dt_hours: float = 0.25,
    battery_capacity_wh: float = 5120,
    soc_min: float = 0.10,
    soc_max: float = 0.95,
    max_charge_w: float = 2500,
    max_discharge_w: float = 2500,
    charge_eff: float = 0.95,
    discharge_eff: float = 0.95,
    initial_soc: float = 0.50,
    tariff_per_kwh: float = 1.20,
) -> pd.DataFrame:
    """
    Run the rule-based EMS over a time series.

    Parameters
    ----------
    pv_power, load_power : np.ndarray
        PV generation and building load at each time step (W).
    dt_hours : float
        Time step duration in hours.
    tariff_per_kwh : float
        Flat electricity tariff (MAD/kWh).

    Returns
    -------
    pd.DataFrame with columns: soc, battery_power, grid_power, cost, etc.
    """
    n = len(pv_power)
    soc = np.zeros(n)
    bat_power = np.zeros(n)
    grid_power = np.zeros(n)
    cost = np.zeros(n)

    current_soc = initial_soc

    for t in range(n):
        pv = pv_power[t]
        load = load_power[t]
        net = pv - load

        if net > 0:
            # Surplus → charge battery
            surplus = net
            soc_room = (soc_max - current_soc) * battery_capacity_wh
            max_charge_energy = min(max_charge_w * dt_hours, soc_room / charge_eff)
            charge = min(surplus * dt_hours, max_charge_energy) / dt_hours

            bat_power[t] = charge
            grid_power[t] = 0.0
            current_soc += (charge_eff * charge * dt_hours) / battery_capacity_wh

        else:
            # Deficit → discharge battery
            deficit = -net
            soc_available = (current_soc - soc_min) * battery_capacity_wh
            max_dis_energy = min(max_discharge_w * dt_hours, soc_available * discharge_eff)
            discharge = min(deficit * dt_hours, max_dis_energy) / dt_hours

            bat_power[t] = -discharge
            grid_power[t] = max(deficit - discharge, 0.0)
            current_soc -= (discharge * dt_hours) / (discharge_eff * battery_capacity_wh)

        current_soc = np.clip(current_soc, soc_min, soc_max)
        soc[t] = current_soc
        cost[t] = grid_power[t] * dt_hours / 1000.0 * tariff_per_kwh

    return pd.DataFrame({
        "soc_pct": np.round(soc * 100, 2),
        "battery_power_w": np.round(bat_power, 1),
        "grid_power_w": np.round(grid_power, 1),
        "cost_mad": np.round(cost, 4),
    })
