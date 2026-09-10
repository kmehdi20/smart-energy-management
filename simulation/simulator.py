"""
Main simulator — orchestrates weather, PV, load, and battery simulation
to produce a complete synthetic dataset.

Usage:
    python -m simulation.simulator --days 90 --output ml/data/raw/synthetic_90d.csv
    python -m simulation.simulator --scenario sunny_summer --days 7
"""

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .profiles import (
    WeatherParams, generate_weather_profile,
    PVParams, generate_pv_profile,
    LoadParams, generate_load_profile,
)
from .battery_sim import BatteryParams, simulate_battery
from .scenarios import SCENARIO_MAP, SUNNY_SUMMER, Scenario

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Project root (two levels up from this file)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "settings.yaml"


def load_config() -> dict:
    """Load project configuration from settings.yaml."""
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)


def build_timestamps(
    start_date: str,
    days: int,
    step_minutes: int = 15,
    tz: str = "Africa/Casablanca",
) -> pd.DatetimeIndex:
    """Create a DatetimeIndex for the simulation period."""
    start = pd.Timestamp(start_date, tz=tz)
    end = start + pd.Timedelta(days=days)
    return pd.date_range(
        start=start,
        end=end,
        freq=f"{step_minutes}min",
        inclusive="left",
    )


def simulate_day_type(day_of_year: int, total_days: int) -> str:
    """
    Assign a scenario type based on day of year for multi-day simulation.
    Creates seasonal variation in a 90-day dataset.
    """
    # Rough mapping: day 1-30 = late summer, 31-60 = autumn, 61-90 = early winter
    # Adjust for any start date
    fraction = (day_of_year % 365) / 365.0

    # Summer: May–September (fraction 0.33–0.75)
    if 0.33 <= fraction <= 0.75:
        return "sunny_summer"
    # Winter: November–February (fraction 0.83–1.0, 0.0–0.17)
    elif fraction >= 0.83 or fraction <= 0.17:
        return "cloudy_winter"
    else:
        return "spring_mild"


def run_simulation(
    days: int = 90,
    start_date: str = "2026-01-01",
    scenario: Scenario | None = None,
    seed: int = 42,
    step_minutes: int = 15,
    tz: str = "Africa/Casablanca",
) -> pd.DataFrame:
    """
    Run a full simulation and return the combined dataset.

    Parameters
    ----------
    days : int
        Number of days to simulate.
    start_date : str
        Start date (ISO format).
    scenario : Scenario or None
        If provided, use this scenario for all days.
        If None, vary scenarios by season automatically.
    seed : int
        Random seed for reproducibility.
    step_minutes : int
        Time step in minutes.
    tz : str
        Timezone string.

    Returns
    -------
    pd.DataFrame
        Complete dataset with all columns.
    """
    rng = np.random.default_rng(seed)
    timestamps = build_timestamps(start_date, days, step_minutes, tz)
    logger.info(
        f"Simulating {days} days ({len(timestamps)} steps) "
        f"from {start_date}, step={step_minutes} min"
    )

    # If a single scenario is given, use its params for the entire period
    if scenario is not None:
        weather_params = scenario.weather
        load_params = scenario.load
        logger.info(f"Using fixed scenario: {scenario.name}")

        weather_df = generate_weather_profile(timestamps, weather_params, rng)
        pv_df = generate_pv_profile(weather_df, PVParams(), rng)
        load_df = generate_load_profile(timestamps, load_params, rng)

    else:
        # Day-by-day scenario variation for realistic multi-month dataset
        logger.info("Using seasonal scenario variation")
        weather_frames = []
        pv_frames = []
        load_frames = []

        for day_offset in range(days):
            day_start = pd.Timestamp(start_date, tz=tz) + pd.Timedelta(days=day_offset)
            day_end = day_start + pd.Timedelta(days=1)
            day_ts = timestamps[(timestamps >= day_start) & (timestamps < day_end)]

            if len(day_ts) == 0:
                continue

            doy = day_start.timetuple().tm_yday
            scenario_name = simulate_day_type(doy, days)

            # Add some random variation to cloud cover
            sc = SCENARIO_MAP[scenario_name]
            wp = WeatherParams(
                latitude_deg=sc.weather.latitude_deg,
                longitude_deg=sc.weather.longitude_deg,
                altitude_m=sc.weather.altitude_m,
                cloud_factor=np.clip(
                    sc.weather.cloud_factor + rng.normal(0, 0.15), 0, 1
                ),
                temp_min_c=sc.weather.temp_min_c + rng.normal(0, 2),
                temp_max_c=sc.weather.temp_max_c + rng.normal(0, 2),
                humidity_min_pct=sc.weather.humidity_min_pct,
                humidity_max_pct=sc.weather.humidity_max_pct,
            )

            # Weekend detection
            lp = LoadParams(
                load_multiplier=sc.load.load_multiplier * (1 + rng.normal(0, 0.05)),
                ac_active=sc.load.ac_active,
                is_weekend=day_start.weekday() >= 5,
            )

            w = generate_weather_profile(day_ts, wp, rng)
            p = generate_pv_profile(w, PVParams(), rng)
            lo = generate_load_profile(day_ts, lp, rng)

            weather_frames.append(w)
            pv_frames.append(p)
            load_frames.append(lo)

        weather_df = pd.concat(weather_frames, ignore_index=True)
        pv_df = pd.concat(pv_frames, ignore_index=True)
        load_df = pd.concat(load_frames, ignore_index=True)

    # Battery simulation (rule-based baseline)
    battery_df = simulate_battery(
        pv_power=pv_df["pv_power_w"].values,
        load_power=load_df["load_power_w"].values,
        params=BatteryParams(),
        dt_hours=step_minutes / 60.0,
    )

    # Combine all into a single DataFrame
    combined = pd.DataFrame({
        "timestamp": weather_df["timestamp"],
        # Weather
        "irradiance_wm2": weather_df["irradiance_wm2"],
        "temperature_c": weather_df["temperature_c"],
        "humidity_pct": weather_df["humidity_pct"],
        # PV
        "pv_power_w": pv_df["pv_power_w"],
        "pv_voltage_v": pv_df["pv_voltage_v"],
        "pv_current_a": pv_df["pv_current_a"],
        # Load
        "load_power_w": load_df["load_power_w"],
        "base_load_w": load_df["base_load_w"],
        "variable_load_w": load_df["variable_load_w"],
        "ac_load_w": load_df["ac_load_w"],
        "flexible_load_w": load_df["flexible_load_w"],
        # Battery
        "soc_pct": battery_df["soc_pct"],
        "battery_power_w": battery_df["battery_power_w"],
        "battery_voltage_v": battery_df["battery_voltage_v"],
        "battery_current_a": battery_df["battery_current_a"],
        # Grid
        "grid_power_w": battery_df["grid_power_w"],
        # Energy flows
        "pv_to_load_w": battery_df["pv_to_load_w"],
        "pv_to_battery_w": battery_df["pv_to_battery_w"],
        "battery_to_load_w": battery_df["battery_to_load_w"],
        "pv_curtailed_w": battery_df["pv_curtailed_w"],
    })

    # Add derived columns
    dt_h = step_minutes / 60.0
    combined["grid_energy_kwh"] = combined["grid_power_w"] * dt_h / 1000.0
    combined["pv_energy_kwh"] = combined["pv_power_w"] * dt_h / 1000.0
    combined["load_energy_kwh"] = combined["load_power_w"] * dt_h / 1000.0

    # Mark as synthetic
    combined["data_source"] = "synthetic"

    logger.info(f"Dataset generated: {len(combined)} rows, {combined.columns.size} columns")
    return combined


def inject_anomalies(
    df: pd.DataFrame,
    rng: np.random.Generator,
    n_anomalies: int = 15,
) -> pd.DataFrame:
    """
    Inject synthetic anomalies for anomaly detection training/testing.

    Anomaly types:
    1. Night consumption spike (02:00–04:00)
    2. Unexpectedly high daytime load (3× normal)
    3. PV drop during clear conditions

    Returns a copy with an 'is_anomaly' boolean column and modified values.
    """
    df = df.copy()
    df["is_anomaly"] = False
    n = len(df)

    for _ in range(n_anomalies):
        anom_type = rng.choice(["night_spike", "high_load", "pv_drop"])
        idx = rng.integers(96, n - 96)  # avoid first/last day edges

        if anom_type == "night_spike":
            # Find a nighttime index (00:00–05:00)
            ts = pd.Timestamp(df.iloc[idx]["timestamp"])
            night_mask = df["timestamp"].apply(
                lambda t: 0 <= pd.Timestamp(t).hour <= 4
            )
            night_indices = df.index[night_mask]
            if len(night_indices) == 0:
                continue
            idx = rng.choice(night_indices)
            # Spike 4 consecutive steps (1 hour)
            end_idx = min(idx + 4, n)
            df.loc[idx:end_idx - 1, "load_power_w"] *= rng.uniform(3.0, 5.0)
            df.loc[idx:end_idx - 1, "is_anomaly"] = True

        elif anom_type == "high_load":
            end_idx = min(idx + 8, n)  # 2 hours
            df.loc[idx:end_idx - 1, "load_power_w"] *= rng.uniform(2.5, 4.0)
            df.loc[idx:end_idx - 1, "is_anomaly"] = True

        elif anom_type == "pv_drop":
            # Drop PV during daytime
            ts = pd.Timestamp(df.iloc[idx]["timestamp"])
            day_mask = df["timestamp"].apply(
                lambda t: 10 <= pd.Timestamp(t).hour <= 15
            )
            day_indices = df.index[day_mask & (df["pv_power_w"] > 500)]
            if len(day_indices) == 0:
                continue
            idx = rng.choice(day_indices)
            end_idx = min(idx + 6, n)
            df.loc[idx:end_idx - 1, "pv_power_w"] *= rng.uniform(0.05, 0.2)
            df.loc[idx:end_idx - 1, "is_anomaly"] = True

    anomaly_count = df["is_anomaly"].sum()
    logger.info(f"Injected anomalies: {anomaly_count} affected time steps")
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic energy management dataset"
    )
    parser.add_argument(
        "--days", type=int, default=90,
        help="Number of days to simulate (default: 90)"
    )
    parser.add_argument(
        "--start-date", type=str, default="2026-01-01",
        help="Simulation start date (default: 2026-01-01)"
    )
    parser.add_argument(
        "--scenario", type=str, default=None,
        choices=list(SCENARIO_MAP.keys()),
        help="Use a fixed scenario for all days (default: seasonal variation)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed (default: 42)"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output CSV path (default: ml/data/raw/synthetic_{days}d.csv)"
    )
    parser.add_argument(
        "--anomalies", type=int, default=15,
        help="Number of anomalies to inject (default: 15)"
    )

    args = parser.parse_args()

    scenario = SCENARIO_MAP.get(args.scenario) if args.scenario else None

    df = run_simulation(
        days=args.days,
        start_date=args.start_date,
        scenario=scenario,
        seed=args.seed,
    )

    # Inject anomalies
    rng = np.random.default_rng(args.seed + 1)
    df = inject_anomalies(df, rng, n_anomalies=args.anomalies)

    # Save
    output_path = args.output or str(
        PROJECT_ROOT / "ml" / "data" / "raw" / f"synthetic_{args.days}d.csv"
    )
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(f"Saved to {output_path}")

    # Print summary statistics
    print("\n" + "=" * 60)
    print("DATASET SUMMARY")
    print("=" * 60)
    print(f"Period:          {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")
    print(f"Rows:            {len(df):,}")
    print(f"Time step:       15 min")
    print(f"Data source:     synthetic")
    print(f"Anomalies:       {df['is_anomaly'].sum()} steps flagged")
    print()
    print("── Daily Averages ──")
    steps_per_day = 96
    total_days = len(df) / steps_per_day
    print(f"PV generation:   {df['pv_energy_kwh'].sum() / total_days:.1f} kWh/day")
    print(f"Load consumption:{df['load_energy_kwh'].sum() / total_days:.1f} kWh/day")
    print(f"Grid import:     {df['grid_energy_kwh'].sum() / total_days:.1f} kWh/day")
    pv_total = df["pv_energy_kwh"].sum()
    pv_to_load_total = (df["pv_to_load_w"] * (15 / 60) / 1000).sum()
    self_consumption = (pv_to_load_total / pv_total * 100) if pv_total > 0 else 0
    print(f"PV self-cons.:   {self_consumption:.1f}%")
    print(f"Avg SOC:         {df['soc_pct'].mean():.1f}%")
    print(f"Peak load:       {df['load_power_w'].max():.0f} W")
    print(f"Peak PV:         {df['pv_power_w'].max():.0f} W")
    print("=" * 60)


if __name__ == "__main__":
    main()
