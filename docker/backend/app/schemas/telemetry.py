"""
Pydantic schemas for request/response validation and MQTT payload parsing.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ── MQTT Telemetry Payload ────────────────────────────────

class LoadTelemetry(BaseModel):
    voltage_v: float = Field(ge=0, le=300)
    current_a: float = Field(ge=0, le=200)
    power_w: float = Field(ge=0, le=50000)
    energy_kwh: float = Field(ge=0)
    pf: float = Field(ge=0, le=1, default=1.0)
    freq_hz: float = Field(ge=45, le=55, default=50.0)


class PVTelemetry(BaseModel):
    voltage_v: float = Field(ge=0, le=200)
    current_a: float = Field(ge=0, le=50)
    power_w: float = Field(ge=0, le=10000)


class BatteryTelemetry(BaseModel):
    voltage_v: float = Field(ge=0, le=60)
    current_a: float  # can be negative (discharging)
    soc_pct: float = Field(ge=0, le=100)


class EnvironmentTelemetry(BaseModel):
    temperature_c: float = Field(ge=-20, le=60)
    humidity_pct: float = Field(ge=0, le=100)
    irradiance_wm2: float = Field(ge=0, le=1500, default=0.0)


class TelemetryPayload(BaseModel):
    """Bundled MQTT telemetry message from ESP32 or simulator."""
    timestamp: datetime
    device_id: str
    load: LoadTelemetry | None = None
    pv: PVTelemetry | None = None
    battery: BatteryTelemetry | None = None
    env: EnvironmentTelemetry | None = None

    @field_validator("timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v)
        return v


# ── API Response Schemas ──────────────────────────────────

class DeviceOut(BaseModel):
    device_id: UUID
    name: str
    type: str
    location: str | None
    is_active: bool

    model_config = {"from_attributes": True}


class EnergyFlowOut(BaseModel):
    timestamp: datetime
    pv_power_w: float | None
    load_power_w: float | None
    grid_power_w: float | None
    battery_power_w: float | None
    soc_percent: float | None
    pv_to_load_w: float | None
    pv_to_battery_w: float | None
    battery_to_load_w: float | None
    data_source: str | None

    model_config = {"from_attributes": True}


class AlertOut(BaseModel):
    id: int
    timestamp: datetime
    alert_type: str
    severity: str
    message: str
    acknowledged: bool

    model_config = {"from_attributes": True}


class PredictionOut(BaseModel):
    timestamp: datetime
    prediction_type: str
    model_name: str
    predicted_value_w: float
    actual_value_w: float | None

    model_config = {"from_attributes": True}


class DailyPerformanceOut(BaseModel):
    date: datetime
    strategy: str
    pv_generation_kwh: float | None
    load_consumption_kwh: float | None
    grid_import_kwh: float | None
    self_consumption_pct: float | None
    energy_cost_mad: float | None
    co2_avoided_kg: float | None

    model_config = {"from_attributes": True}


class HealthResponse(BaseModel):
    status: str
    database: str
    mqtt: str
