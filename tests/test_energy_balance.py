"""
Unit tests for energy balance calculations.

Verifies that the fundamental energy balance holds:
    PV + Grid + Battery_discharge = Load + Battery_charge + Curtailed
"""

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation.battery_sim import BatteryParams, simulate_battery


class TestEnergyBalance:
    """Test energy balance across different scenarios."""

    def test_balance_sunny_day(self):
        """PV surplus day — energy balance must hold."""
        n = 96
        pv = np.concatenate([
            np.zeros(24),                          # night
            np.linspace(0, 3000, 24),              # morning ramp
            np.linspace(3000, 0, 24),              # afternoon decline
            np.zeros(24),                          # night
        ])
        load = np.full(n, 1000)

        result = simulate_battery(pv, load, BatteryParams())

        bat_dis = (-result["battery_power_w"].values).clip(min=0)
        bat_ch = result["battery_power_w"].values.clip(min=0)
        curtailed = result["pv_curtailed_w"].values

        supply = pv + result["grid_power_w"].values + bat_dis
        demand = load + bat_ch + curtailed
        residual = np.abs(supply - demand)

        assert residual.max() < 1.0, f"Max residual {residual.max():.2f} W exceeds 1 W"

    def test_balance_no_pv(self):
        """No PV — all load from battery then grid."""
        n = 96
        pv = np.zeros(n)
        load = np.full(n, 500)

        result = simulate_battery(pv, load, BatteryParams(initial_soc=0.90))

        bat_dis = (-result["battery_power_w"].values).clip(min=0)
        bat_ch = result["battery_power_w"].values.clip(min=0)

        supply = pv + result["grid_power_w"].values + bat_dis
        demand = load + bat_ch
        residual = np.abs(supply - demand)

        assert residual.max() < 1.0

    def test_balance_exact_match(self):
        """PV exactly equals load — no battery or grid needed."""
        n = 96
        pv = np.full(n, 1500)
        load = np.full(n, 1500)

        result = simulate_battery(pv, load, BatteryParams())

        assert np.allclose(result["grid_power_w"].values, 0, atol=1.0)
        assert np.allclose(result["battery_power_w"].values, 0, atol=1.0)

    def test_grid_never_negative(self):
        """Grid import must never be negative (no export)."""
        n = 96
        pv = np.random.default_rng(42).uniform(0, 4000, n)
        load = np.random.default_rng(43).uniform(200, 3000, n)

        result = simulate_battery(pv, load, BatteryParams())

        assert (result["grid_power_w"].values >= -0.01).all(), \
            "Grid power went negative (export not allowed)"


class TestEnergyConservation:
    """Test that total energy is conserved over a full day."""

    def test_total_energy_conservation(self):
        """Sum of all energy sources = sum of all sinks over 24h."""
        n = 96
        dt = 0.25
        rng = np.random.default_rng(42)
        pv = np.maximum(rng.normal(2000, 500, n), 0)
        load = np.maximum(rng.normal(1500, 300, n), 200)

        result = simulate_battery(pv, load, BatteryParams(initial_soc=0.50))

        pv_energy = (pv * dt).sum()
        grid_energy = (result["grid_power_w"].values * dt).sum()
        bat_dis_energy = ((-result["battery_power_w"].values).clip(min=0) * dt).sum()
        load_energy = (load * dt).sum()
        bat_ch_energy = (result["battery_power_w"].values.clip(min=0) * dt).sum()
        curtailed_energy = (result["pv_curtailed_w"].values * dt).sum()

        total_supply = pv_energy + grid_energy + bat_dis_energy
        total_demand = load_energy + bat_ch_energy + curtailed_energy

        assert abs(total_supply - total_demand) < 10.0, \
            f"Energy mismatch: supply={total_supply:.1f} Wh, demand={total_demand:.1f} Wh"
