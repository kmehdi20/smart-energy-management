"""
SQLAlchemy ORM models for all database tables.

Compatible with both SQLite (dev) and PostgreSQL (production).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float,
    Integer, String, Text, JSON,
)
from sqlalchemy.sql import func

from ..database import Base


def _new_uuid() -> str:
    """Generate a UUID string (works with both SQLite and PostgreSQL)."""
    return str(uuid.uuid4())


class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String(36), primary_key=True, default=_new_uuid)
    name = Column(String(100), nullable=False)
    type = Column(String(50), nullable=False)
    location = Column(String(200))
    created_at = Column(DateTime, server_default=func.now())
    is_active = Column(Boolean, default=True)


class Measurement(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(36), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    voltage_v = Column(Float)
    current_a = Column(Float)
    power_w = Column(Float)
    energy_kwh = Column(Float)
    power_factor = Column(Float)
    frequency_hz = Column(Float)
    created_at = Column(DateTime, server_default=func.now())


class PVMeasurement(Base):
    __tablename__ = "pv_measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(36), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    pv_voltage_v = Column(Float)
    pv_current_a = Column(Float)
    pv_power_w = Column(Float)
    created_at = Column(DateTime, server_default=func.now())


class BatteryStatus(Base):
    __tablename__ = "battery_status"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(36), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    voltage_v = Column(Float)
    current_a = Column(Float)
    power_w = Column(Float)
    soc_percent = Column(Float)
    created_at = Column(DateTime, server_default=func.now())


class EnvironmentalData(Base):
    __tablename__ = "environmental_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(36), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    temperature_c = Column(Float)
    humidity_percent = Column(Float)
    irradiance_wm2 = Column(Float)
    created_at = Column(DateTime, server_default=func.now())


class EnergyFlow(Base):
    __tablename__ = "energy_flows"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(36), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    pv_power_w = Column(Float)
    load_power_w = Column(Float)
    grid_power_w = Column(Float)
    battery_power_w = Column(Float)
    pv_to_load_w = Column(Float)
    pv_to_battery_w = Column(Float)
    battery_to_load_w = Column(Float)
    pv_curtailed_w = Column(Float)
    soc_percent = Column(Float)
    data_source = Column(String(20), default="real")
    created_at = Column(DateTime, server_default=func.now())


class Prediction(Base):
    __tablename__ = "predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    prediction_type = Column(String(30), nullable=False)
    model_name = Column(String(50), nullable=False)
    predicted_value_w = Column(Float, nullable=False)
    actual_value_w = Column(Float)


class OptimizationResult(Base):
    __tablename__ = "optimization_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    created_at = Column(DateTime, server_default=func.now())
    horizon_start = Column(DateTime, nullable=False)
    horizon_end = Column(DateTime, nullable=False)
    strategy = Column(String(20), nullable=False)
    schedule_json = Column(JSON, nullable=False)
    expected_cost_mad = Column(Float)
    expected_grid_kwh = Column(Float)
    actual_cost_mad = Column(Float)
    actual_grid_kwh = Column(Float)


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(10), nullable=False)
    message = Column(Text, nullable=False)
    details_json = Column(JSON)
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())


class DailyPerformance(Base):
    __tablename__ = "daily_performance"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)
    strategy = Column(String(20), nullable=False)
    pv_generation_kwh = Column(Float)
    load_consumption_kwh = Column(Float)
    grid_import_kwh = Column(Float)
    grid_export_kwh = Column(Float, default=0)
    battery_charge_kwh = Column(Float)
    battery_discharge_kwh = Column(Float)
    self_consumption_pct = Column(Float)
    self_sufficiency_pct = Column(Float)
    peak_demand_w = Column(Float)
    energy_cost_mad = Column(Float)
    co2_avoided_kg = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
