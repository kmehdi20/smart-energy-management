"""
Unit tests for the simulation module.

Verifies synthetic data generation, profile shapes, and anomaly injection.
"""

import numpy as np
import pandas as pd
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from simulation.simulator import run_simulation, inject_anomalies
from simulation.profiles.weather_profile import WeatherParams, generate_weather_profile
from simulation.profiles.pv_profile import PVParams, generate_pv_profile
from simulation.profiles.load_profile import LoadParams, generate_load_profile


class TestSimulatorOutput:
    """Verify simulator produces correct output format."""

    def test_output_columns(self):
        """Simulator must produce all required columns."""
        df = run_simulation(days=1, seed=42)
        required = [
            "timestamp", "irradiance_wm2", "temperature_c", "humidity_pct",
            "pv_power_w", "load_power_w", "soc_pct", "battery_power_w",
            "grid_power_w", "data_source",
        ]
        for col in required:
            assert col in df.columns, f"Missing column: {col}"

    def test_output_length(self):
        """1 day = 96 rows at 15-min resolution."""
        df = run_simulation(days=1, seed=42)
        assert len(df) == 96

        df7 = run_simulation(days=7, seed=42)
        assert len(df7) == 7 * 96

    def test_data_source_label(self):
        """All rows must be labeled as synthetic."""
        df = run_simulation(days=1, seed=42)
        assert (df["data_source"] == "synthetic").all()

    def test_reproducibility(self):
        """Same seed should produce identical output."""
        df1 = run_simulation(days=3, seed=42)
        df2 = run_simulation(days=3, seed=42)
        pd.testing.assert_frame_equal(df1, df2)


class TestWeatherProfile:
    """Verify weather profile realism."""

    def test_irradiance_zero_at_night(self):
        """No irradiance between 22:00 and 04:00."""
        ts = pd.date_range("2026-06-15", periods=96, freq="15min", tz="Africa/Casablanca")
        rng = np.random.default_rng(42)
        df = generate_weather_profile(ts, WeatherParams(), rng)

        night = df[df["timestamp"].dt.hour.isin([0, 1, 2, 3, 22, 23])]
        assert (night["irradiance_wm2"] < 5).all(), \
            "Irradiance should be ~0 at night"

    def test_irradiance_positive_midday(self):
        """Irradiance should be positive around solar noon."""
        ts = pd.date_range("2026-06-15", periods=96, freq="15min", tz="Africa/Casablanca")
        rng = np.random.default_rng(42)
        df = generate_weather_profile(ts, WeatherParams(cloud_factor=0.0), rng)

        midday = df[df["timestamp"].dt.hour.isin([11, 12, 13])]
        assert (midday["irradiance_wm2"] > 100).all(), \
            "Clear-sky midday irradiance should be > 100 W/m2"


class TestPVProfile:
    """Verify PV profile follows irradiance."""

    def test_pv_zero_when_dark(self):
        """PV power must be 0 when irradiance is 0."""
        ts = pd.date_range("2026-06-15", periods=96, freq="15min", tz="Africa/Casablanca")
        rng = np.random.default_rng(42)
        weather = generate_weather_profile(ts, WeatherParams(), rng)
        pv = generate_pv_profile(weather, PVParams(), rng)

        dark = weather["irradiance_wm2"] < 1
        assert (pv.loc[dark, "pv_power_w"] < 1).all(), \
            "PV power should be 0 when irradiance is 0"

    def test_pv_below_peak(self):
        """PV power must not exceed rated peak capacity significantly."""
        ts = pd.date_range("2026-06-15", periods=96, freq="15min", tz="Africa/Casablanca")
        rng = np.random.default_rng(42)
        weather = generate_weather_profile(ts, WeatherParams(cloud_factor=0.0), rng)
        pv = generate_pv_profile(weather, PVParams(peak_power_w=4000), rng)

        # With inverter efficiency and temperature derating, should stay under ~4200
        assert pv["pv_power_w"].max() < 4500, \
            f"PV peak {pv['pv_power_w'].max():.0f} W exceeds reasonable limit"


class TestLoadProfile:
    """Verify load profile patterns."""

    def test_base_load_always_present(self):
        """Load should never drop below base load."""
        ts = pd.date_range("2026-06-15", periods=96, freq="15min", tz="Africa/Casablanca")
        rng = np.random.default_rng(42)
        load = generate_load_profile(ts, LoadParams(base_load_w=200), rng)

        assert load["load_power_w"].min() >= 190, \
            f"Load dropped to {load['load_power_w'].min():.0f} W, below base"

    def test_evening_peak_higher(self):
        """Evening load should be higher than early morning."""
        ts = pd.date_range("2026-06-15", periods=96, freq="15min", tz="Africa/Casablanca")
        rng = np.random.default_rng(42)
        load = generate_load_profile(ts, LoadParams(), rng)

        early = load[load["timestamp"].dt.hour.isin([2, 3, 4])]["load_power_w"].mean()
        evening = load[load["timestamp"].dt.hour.isin([19, 20, 21])]["load_power_w"].mean()

        assert evening > early * 2, \
            f"Evening load {evening:.0f} W should be much higher than night {early:.0f} W"


class TestAnomalyInjection:
    """Verify anomaly injection works correctly."""

    def test_anomalies_flagged(self):
        """Injected anomalies should be marked in is_anomaly column."""
        df = run_simulation(days=30, seed=42)
        rng = np.random.default_rng(100)
        df = inject_anomalies(df, rng, n_anomalies=10)

        assert "is_anomaly" in df.columns
        assert df["is_anomaly"].sum() > 0, "No anomalies were injected"

    def test_anomaly_values_elevated(self):
        """Anomaly rows should have higher-than-normal load."""
        df = run_simulation(days=30, seed=42)
        normal_mean = df["load_power_w"].mean()

        rng = np.random.default_rng(100)
        df = inject_anomalies(df, rng, n_anomalies=10)

        anomaly_mean = df[df["is_anomaly"]]["load_power_w"].mean()
        # Anomalies include load spikes, so mean should be higher
        # (some may be PV drops which don't raise load, so use > instead of >>)
        assert anomaly_mean > normal_mean, \
            "Anomaly load should generally be elevated"
