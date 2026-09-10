"""
Unit tests for battery State of Charge model.

Verifies SOC bounds, efficiency losses, power limits,
and correct charge/discharge behavior.
"""

import numpy as np
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation.battery_sim import BatteryParams, simulate_battery


class TestSOCBounds:
    """SOC must always stay within [SOC_min, SOC_max]."""

    def test_soc_never_below_minimum(self):
        """Heavy load, no PV — SOC must not drop below SOC_min."""
        n = 96 * 3  # 3 days
        pv = np.zeros(n)
        load = np.full(n, 2000)  # constant heavy load

        result = simulate_battery(pv, load, BatteryParams(initial_soc=0.90))
        soc = result["soc_pct"].values / 100.0

        assert soc.min() >= 0.10 - 0.001, \
            f"SOC dropped to {soc.min():.4f}, below minimum 0.10"

    def test_soc_never_above_maximum(self):
        """Heavy PV, no load — SOC must not exceed SOC_max."""
        n = 96
        pv = np.full(n, 4000)
        load = np.full(n, 100)  # minimal load

        result = simulate_battery(pv, load, BatteryParams(initial_soc=0.50))
        soc = result["soc_pct"].values / 100.0

        assert soc.max() <= 0.95 + 0.001, \
            f"SOC rose to {soc.max():.4f}, above maximum 0.95"

    def test_initial_soc_respected(self):
        """First SOC value should be close to initial_soc after one step."""
        pv = np.array([0.0])
        load = np.array([0.0])

        for init in [0.20, 0.50, 0.80]:
            result = simulate_battery(pv, load, BatteryParams(initial_soc=init))
            assert abs(result["soc_pct"].values[0] / 100.0 - init) < 0.01


class TestChargingEfficiency:
    """Verify efficiency losses during charging and discharging."""

    def test_charging_loses_energy(self):
        """Energy stored in battery < energy delivered to battery (eta < 1)."""
        n = 96
        pv = np.full(n, 3000)
        load = np.full(n, 500)

        params = BatteryParams(initial_soc=0.20, charge_eff=0.95)
        result = simulate_battery(pv, load, params)

        charge_power = result["battery_power_w"].values.clip(min=0)
        energy_in = (charge_power * 0.25).sum()  # Wh delivered

        soc_start = 0.20
        soc_end = result["soc_pct"].values[-1] / 100.0
        energy_stored = (soc_end - soc_start) * params.capacity_wh

        # Energy stored should be less than energy delivered
        assert energy_stored < energy_in, \
            f"Stored {energy_stored:.0f} Wh >= delivered {energy_in:.0f} Wh (no efficiency loss)"

    def test_discharging_delivers_less(self):
        """Energy delivered to load < energy removed from battery (eta < 1)."""
        n = 96
        pv = np.zeros(n)
        load = np.full(n, 1000)

        params = BatteryParams(initial_soc=0.90, discharge_eff=0.95)
        result = simulate_battery(pv, load, params)

        discharge_power = (-result["battery_power_w"].values).clip(min=0)
        energy_delivered = (discharge_power * 0.25).sum()

        soc_start = 0.90
        soc_end = result["soc_pct"].values[-1] / 100.0
        energy_removed = (soc_start - soc_end) * params.capacity_wh

        # Energy removed from battery > energy delivered to load
        assert energy_removed > energy_delivered * 0.99, \
            "Discharge efficiency not applied correctly"


class TestPowerLimits:
    """Battery charge/discharge power must respect max limits."""

    def test_charge_power_limited(self):
        """Charging power must not exceed max_charge_w."""
        n = 96
        pv = np.full(n, 10000)  # massive surplus
        load = np.full(n, 100)

        params = BatteryParams(max_charge_w=2500, initial_soc=0.20)
        result = simulate_battery(pv, load, params)

        charge = result["battery_power_w"].values.clip(min=0)
        assert charge.max() <= params.max_charge_w + 1.0, \
            f"Charge power {charge.max():.0f} W exceeds limit {params.max_charge_w} W"

    def test_discharge_power_limited(self):
        """Discharge power must not exceed max_discharge_w."""
        n = 96
        pv = np.zeros(n)
        load = np.full(n, 10000)  # massive deficit

        params = BatteryParams(max_discharge_w=2500, initial_soc=0.90)
        result = simulate_battery(pv, load, params)

        discharge = (-result["battery_power_w"].values).clip(min=0)
        assert discharge.max() <= params.max_discharge_w + 1.0, \
            f"Discharge power {discharge.max():.0f} W exceeds limit {params.max_discharge_w} W"
