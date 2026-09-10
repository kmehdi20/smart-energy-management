"""
Weather profile generator for Meknès, Morocco (lat 33.9°N).

Generates realistic synthetic irradiance and temperature profiles
using a clear-sky solar model with configurable cloud cover.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass


@dataclass
class WeatherParams:
    """Parameters controlling the weather profile."""
    latitude_deg: float = 33.9
    longitude_deg: float = -5.55
    altitude_m: float = 550
    cloud_factor: float = 0.0      # 0 = clear sky, 1 = fully overcast
    temp_min_c: float = 18.0       # daily minimum temperature
    temp_max_c: float = 35.0       # daily maximum temperature
    humidity_min_pct: float = 25.0
    humidity_max_pct: float = 65.0


def solar_declination(day_of_year: int) -> float:
    """Solar declination angle in radians (Cooper's equation)."""
    return np.radians(23.45 * np.sin(np.radians(360 / 365 * (284 + day_of_year))))


def equation_of_time(day_of_year: int) -> float:
    """Equation of time correction in minutes."""
    b = np.radians(360 / 365 * (day_of_year - 81))
    return 9.87 * np.sin(2 * b) - 7.53 * np.cos(b) - 1.5 * np.sin(b)


def hour_angle(solar_hour: float) -> float:
    """Hour angle in radians. solar_hour is in hours (12 = solar noon)."""
    return np.radians(15.0 * (solar_hour - 12.0))


def solar_elevation(latitude_rad: float, declination_rad: float,
                    hour_angle_rad: float) -> float:
    """Solar elevation angle in radians."""
    sin_elev = (np.sin(latitude_rad) * np.sin(declination_rad) +
                np.cos(latitude_rad) * np.cos(declination_rad) *
                np.cos(hour_angle_rad))
    return np.arcsin(np.clip(sin_elev, -1.0, 1.0))


def clear_sky_irradiance(elevation_rad: float, altitude_m: float = 550) -> float:
    """
    Simplified clear-sky GHI model (Hottel's method approximation).

    Returns global horizontal irradiance in W/m².
    """
    if elevation_rad <= 0:
        return 0.0

    # Extraterrestrial irradiance on horizontal surface
    solar_constant = 1361.0  # W/m²
    sin_elev = np.sin(elevation_rad)

    # Atmospheric transmittance (simplified Hottel for mid-latitude)
    # Adjusted for altitude
    a0 = 0.4237 - 0.00821 * (6.0 - altitude_m / 1000) ** 2
    a1 = 0.5055 + 0.00595 * (6.5 - altitude_m / 1000) ** 2
    k = 0.2711 + 0.01858 * (2.5 - altitude_m / 1000) ** 2

    # Air mass (Kasten & Young)
    elevation_deg = np.degrees(elevation_rad)
    if elevation_deg < 1.0:
        air_mass = 30.0  # cap at very low angles
    else:
        air_mass = 1.0 / (sin_elev + 0.50572 * (elevation_deg + 6.07995) ** (-1.6364))

    transmittance = a0 + a1 * np.exp(-k * air_mass)
    ghi = solar_constant * sin_elev * transmittance

    return max(ghi, 0.0)


def generate_weather_profile(
    timestamps: pd.DatetimeIndex,
    params: WeatherParams,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """
    Generate weather data (irradiance, temperature, humidity) for given timestamps.

    Parameters
    ----------
    timestamps : pd.DatetimeIndex
        Timestamps (timezone-aware recommended).
    params : WeatherParams
        Weather configuration.
    rng : np.random.Generator
        Random number generator for reproducibility.

    Returns
    -------
    pd.DataFrame
        Columns: timestamp, irradiance_wm2, temperature_c, humidity_pct
    """
    lat_rad = np.radians(params.latitude_deg)

    irradiance = np.zeros(len(timestamps))
    temperature = np.zeros(len(timestamps))
    humidity = np.zeros(len(timestamps))

    for i, ts in enumerate(timestamps):
        doy = ts.timetuple().tm_yday
        hour_decimal = ts.hour + ts.minute / 60.0

        # Solar geometry
        decl = solar_declination(doy)
        eot = equation_of_time(doy)

        # Approximate solar time (simplified — ignoring longitude correction
        # for synthetic data; the shift is ~22 min for Meknès vs UTC+1 meridian)
        solar_time = hour_decimal + eot / 60.0
        ha = hour_angle(solar_time)
        elev = solar_elevation(lat_rad, decl, ha)

        # Clear-sky irradiance
        ghi_clear = clear_sky_irradiance(elev, params.altitude_m)

        # Apply cloud factor (reduces irradiance)
        # Cloud factor with some temporal variation
        cloud_noise = rng.normal(0, 0.05)
        effective_cloud = np.clip(params.cloud_factor + cloud_noise, 0, 1)
        ghi = ghi_clear * (1.0 - 0.75 * effective_cloud)

        # Add sensor noise
        ghi = max(0.0, ghi + rng.normal(0, ghi * 0.02))
        irradiance[i] = round(ghi, 1)

        # Temperature model: sinusoidal with peak at ~15:00
        temp_amplitude = (params.temp_max_c - params.temp_min_c) / 2.0
        temp_mean = (params.temp_max_c + params.temp_min_c) / 2.0
        # Peak at 15:00 → phase shift
        temp = temp_mean + temp_amplitude * np.sin(
            np.radians((hour_decimal - 9.0) / 24.0 * 360.0)
        )
        temp += rng.normal(0, 0.5)  # noise
        temperature[i] = round(temp, 1)

        # Humidity: inversely correlated with temperature
        hum_mean = (params.humidity_min_pct + params.humidity_max_pct) / 2.0
        hum_amplitude = (params.humidity_max_pct - params.humidity_min_pct) / 2.0
        hum = hum_mean - hum_amplitude * np.sin(
            np.radians((hour_decimal - 9.0) / 24.0 * 360.0)
        )
        hum += rng.normal(0, 2.0)
        humidity[i] = round(np.clip(hum, 10, 100), 1)

    return pd.DataFrame({
        "timestamp": timestamps,
        "irradiance_wm2": irradiance,
        "temperature_c": temperature,
        "humidity_pct": humidity,
    })
