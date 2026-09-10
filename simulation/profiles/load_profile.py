"""
Building load consumption profile generator.

Generates realistic residential load curves for a Moroccan building
with critical, non-critical, and flexible loads.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field


@dataclass
class LoadParams:
    """Parameters controlling load profile shape."""
    # Base load (always-on: refrigerator compressor cycling, router, standby)
    base_load_w: float = 200.0

    # Scale factor applied to the entire profile
    load_multiplier: float = 1.0

    # Whether AC is active (summer vs winter)
    ac_active: bool = True
    ac_power_w: float = 1500.0

    # Whether it's a weekend (changes pattern)
    is_weekend: bool = False

    # Flexible loads — these are scheduled separately by the optimizer;
    # in the baseline (no optimization) they run at fixed default times.
    flexible_defaults: list = field(default_factory=lambda: [
        {"name": "Water Heater", "power_w": 2000, "duration_h": 1.5,
         "default_start_hour": 7.0},
        {"name": "Washing Machine", "power_w": 500, "duration_h": 1.5,
         "default_start_hour": 10.0},
        {"name": "Water Pump", "power_w": 750, "duration_h": 1.0,
         "default_start_hour": 7.0},
    ])


# Hourly load shape factors (fraction of non-base load that is active).
# Index = hour (0–23). Represents a typical weekday pattern.
_WEEKDAY_SHAPE = np.array([
    0.05, 0.05, 0.05, 0.05, 0.05, 0.10,  # 00–05: night
    0.25, 0.50, 0.55, 0.30, 0.25, 0.25,  # 06–11: morning
    0.30, 0.30, 0.25, 0.20, 0.25, 0.40,  # 12–17: afternoon
    0.70, 0.85, 1.00, 0.90, 0.60, 0.25,  # 18–23: evening peak
])

_WEEKEND_SHAPE = np.array([
    0.05, 0.05, 0.05, 0.05, 0.05, 0.05,  # 00–05: night
    0.15, 0.30, 0.45, 0.50, 0.55, 0.55,  # 06–11: late morning
    0.50, 0.45, 0.40, 0.35, 0.40, 0.55,  # 12–17: afternoon
    0.75, 0.90, 1.00, 0.95, 0.70, 0.35,  # 18–23: evening peak
])

# Variable load amplitude (W) — the part that follows the shape curve.
# This represents lighting + TV + computer + cooking + misc.
_VARIABLE_LOAD_PEAK_W = 1800.0


def _interpolate_shape(shape_24h: np.ndarray, hour_decimal: float) -> float:
    """Linearly interpolate the hourly shape to sub-hourly resolution."""
    h_floor = int(hour_decimal) % 24
    h_ceil = (h_floor + 1) % 24
    frac = hour_decimal - int(hour_decimal)
    return shape_24h[h_floor] * (1 - frac) + shape_24h[h_ceil] * frac


def generate_load_profile(
    timestamps: pd.DatetimeIndex,
    params: LoadParams,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Generate building load consumption profile.

    The profile consists of:
    1. Base load (continuous)
    2. Variable load (follows hourly shape curve)
    3. AC load (if active, added during hot afternoon hours)
    4. Flexible loads (at default start times in baseline mode)

    Parameters
    ----------
    timestamps : pd.DatetimeIndex
        Simulation timestamps.
    params : LoadParams
        Load configuration.
    rng : np.random.Generator
        Random number generator.

    Returns
    -------
    pd.DataFrame
        Columns: timestamp, load_power_w, base_load_w, variable_load_w,
                 ac_load_w, flexible_load_w
    """
    shape = _WEEKEND_SHAPE if params.is_weekend else _WEEKDAY_SHAPE
    n = len(timestamps)

    base = np.full(n, params.base_load_w)
    variable = np.zeros(n)
    ac = np.zeros(n)
    flexible = np.zeros(n)

    for i, ts in enumerate(timestamps):
        hour_dec = ts.hour + ts.minute / 60.0

        # Variable load from shape curve
        factor = _interpolate_shape(shape, hour_dec)
        var_load = _VARIABLE_LOAD_PEAK_W * factor
        # Add noise (±10%)
        var_load *= (1 + rng.normal(0, 0.10))
        variable[i] = max(var_load, 0.0)

        # AC load: active 12:00–21:00 if enabled, cycling pattern
        if params.ac_active and 12.0 <= hour_dec <= 21.0:
            # AC compressor cycles: ~60% duty cycle during active hours
            if rng.random() < 0.60:
                ac[i] = params.ac_power_w * (0.85 + rng.normal(0, 0.05))

        # Flexible loads at default times (baseline — no optimization)
        for fl in params.flexible_defaults:
            start = fl["default_start_hour"]
            end = start + fl["duration_h"]
            if start <= hour_dec < end:
                flexible[i] += fl["power_w"]

    # Apply overall multiplier
    total = (base + variable + ac + flexible) * params.load_multiplier
    total = np.maximum(total, params.base_load_w)  # never below base

    return pd.DataFrame({
        "timestamp": timestamps,
        "load_power_w": np.round(total, 1),
        "base_load_w": np.round(base * params.load_multiplier, 1),
        "variable_load_w": np.round(variable * params.load_multiplier, 1),
        "ac_load_w": np.round(ac * params.load_multiplier, 1),
        "flexible_load_w": np.round(flexible * params.load_multiplier, 1),
    })
