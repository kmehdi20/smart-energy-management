"""
PV production profile generator.

Converts irradiance and temperature into AC power output
for a given PV system specification.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class PVParams:
    """PV system parameters."""
    peak_power_w: float = 4000       # Wp (STC)
    temp_coeff: float = -0.004       # /°C (typical crystalline Si)
    inverter_efficiency: float = 0.96
    stc_irradiance: float = 1000     # W/m²
    stc_temperature: float = 25      # °C
    noct_factor: float = 0.03        # T_cell ≈ T_amb + factor × G


def generate_pv_profile(
    weather_df: pd.DataFrame,
    params: PVParams,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Generate PV power output from weather data.

    Parameters
    ----------
    weather_df : pd.DataFrame
        Must contain columns: timestamp, irradiance_wm2, temperature_c
    params : PVParams
        PV system configuration.
    rng : np.random.Generator
        Random number generator.

    Returns
    -------
    pd.DataFrame
        Columns: timestamp, pv_power_w, pv_voltage_v, pv_current_a
    """
    g = weather_df["irradiance_wm2"].values
    t_amb = weather_df["temperature_c"].values

    # Cell temperature (simplified NOCT model)
    t_cell = t_amb + params.noct_factor * g

    # DC power before inverter
    p_dc = params.peak_power_w * (g / params.stc_irradiance) * (
        1 + params.temp_coeff * (t_cell - params.stc_temperature)
    )
    p_dc = np.maximum(p_dc, 0.0)

    # AC power after inverter
    p_ac = p_dc * params.inverter_efficiency

    # Add small noise (mismatch, dust, partial shading variability)
    noise = rng.normal(1.0, 0.02, size=len(p_ac))
    p_ac = np.maximum(p_ac * noise, 0.0)

    # Synthetic voltage and current (for sensor simulation)
    # Assume Vmp ≈ 36 V per string, 2 strings → ~72 V at MPP
    # Actual values scale with irradiance
    vmp_ref = 72.0  # V at STC
    pv_voltage = np.where(g > 10, vmp_ref * (0.85 + 0.15 * g / params.stc_irradiance), 0.0)
    safe_voltage = np.where(pv_voltage > 0, pv_voltage, 1.0)  # avoid /0
    pv_current = np.where(pv_voltage > 0, p_dc / safe_voltage, 0.0)

    return pd.DataFrame({
        "timestamp": weather_df["timestamp"].values,
        "pv_power_w": np.round(p_ac, 1),
        "pv_voltage_v": np.round(pv_voltage, 1),
        "pv_current_a": np.round(pv_current, 2),
    })
