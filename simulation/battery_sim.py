"""
Battery state-of-charge simulator.

Implements the SOC model from the design document with efficiency losses,
power limits, and SOC bounds. Includes a baseline rule-based dispatch
(Strategy A) for generating training data.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class BatteryParams:
    """Battery system parameters."""
    capacity_wh: float = 5120       # 5.12 kWh in Wh
    soc_min: float = 0.10           # 10%
    soc_max: float = 0.95           # 95%
    max_charge_w: float = 2500
    max_discharge_w: float = 2500
    charge_eff: float = 0.95
    discharge_eff: float = 0.95
    initial_soc: float = 0.50       # 50%
    nominal_voltage: float = 48.0   # V


def simulate_battery(
    pv_power: np.ndarray,
    load_power: np.ndarray,
    params: BatteryParams,
    dt_hours: float = 0.25,
) -> pd.DataFrame:
    """
    Simulate battery dispatch using the rule-based baseline strategy.

    Strategy A (no optimization):
        - If PV > Load → charge battery with surplus (up to limits)
        - If PV < Load → discharge battery to cover deficit (up to limits)
        - Remaining deficit → grid import

    Parameters
    ----------
    pv_power : np.ndarray
        PV AC power at each time step (W).
    load_power : np.ndarray
        Building load at each time step (W).
    params : BatteryParams
        Battery configuration.
    dt_hours : float
        Time step duration in hours (default 0.25 = 15 min).

    Returns
    -------
    pd.DataFrame
        Columns: soc, battery_power_w (positive=charging, negative=discharging),
                 battery_voltage_v, battery_current_a, grid_power_w,
                 pv_to_load_w, pv_to_battery_w, battery_to_load_w,
                 pv_curtailed_w
    """
    n = len(pv_power)
    soc = np.zeros(n)
    bat_power = np.zeros(n)       # positive = charging, negative = discharging
    grid_power = np.zeros(n)
    pv_to_load = np.zeros(n)
    pv_to_battery = np.zeros(n)
    battery_to_load = np.zeros(n)
    pv_curtailed = np.zeros(n)

    current_soc = params.initial_soc

    for i in range(n):
        pv = pv_power[i]
        load = load_power[i]
        net = pv - load  # positive = surplus, negative = deficit

        charge = 0.0
        discharge = 0.0

        if net > 0:
            # PV surplus → try to charge battery
            pv_direct = load
            surplus = net

            # Maximum energy we can charge in this step
            soc_room = (params.soc_max - current_soc) * params.capacity_wh
            max_charge_energy = min(
                params.max_charge_w * dt_hours,
                soc_room / params.charge_eff,
            )
            charge_energy = min(surplus * dt_hours, max_charge_energy)
            charge = charge_energy / dt_hours if dt_hours > 0 else 0.0

            remaining_surplus = surplus - charge
            curtailed = max(remaining_surplus, 0.0)

            pv_to_load[i] = pv_direct
            pv_to_battery[i] = charge
            pv_curtailed[i] = curtailed
            bat_power[i] = charge  # positive = charging
            grid_power[i] = 0.0

            # Update SOC
            current_soc += (params.charge_eff * charge * dt_hours) / params.capacity_wh

        else:
            # Deficit → try to discharge battery
            pv_to_load[i] = pv
            deficit = -net  # positive value

            # Maximum energy we can discharge in this step
            soc_available = (current_soc - params.soc_min) * params.capacity_wh
            max_discharge_energy = min(
                params.max_discharge_w * dt_hours,
                soc_available * params.discharge_eff,
            )
            discharge_energy = min(deficit * dt_hours, max_discharge_energy)
            discharge = discharge_energy / dt_hours if dt_hours > 0 else 0.0

            remaining_deficit = deficit - discharge
            grid_import = max(remaining_deficit, 0.0)

            battery_to_load[i] = discharge
            bat_power[i] = -discharge  # negative = discharging
            grid_power[i] = grid_import

            # Update SOC
            current_soc -= (discharge * dt_hours) / (
                params.discharge_eff * params.capacity_wh
            )

        # Clamp SOC to bounds (safety)
        current_soc = np.clip(current_soc, params.soc_min, params.soc_max)
        soc[i] = current_soc

    # Derive voltage and current for sensor simulation
    # Voltage varies linearly with SOC (simplified): 44V at 0% → 54V at 100%
    bat_voltage = 44.0 + soc * 10.0
    bat_current = np.where(
        bat_voltage > 0,
        bat_power / bat_voltage,
        0.0,
    )

    return pd.DataFrame({
        "soc_pct": np.round(soc * 100, 2),
        "battery_power_w": np.round(bat_power, 1),
        "battery_voltage_v": np.round(bat_voltage, 1),
        "battery_current_a": np.round(bat_current, 2),
        "grid_power_w": np.round(grid_power, 1),
        "pv_to_load_w": np.round(pv_to_load, 1),
        "pv_to_battery_w": np.round(pv_to_battery, 1),
        "battery_to_load_w": np.round(battery_to_load, 1),
        "pv_curtailed_w": np.round(pv_curtailed, 1),
    })
