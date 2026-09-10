-- ============================================================
-- Smart Energy Management System — Database Schema
-- PostgreSQL 15+
-- ============================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Devices ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS devices (
    device_id   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name        VARCHAR(100) NOT NULL,
    type        VARCHAR(50)  NOT NULL CHECK (type IN ('esp32', 'simulator', 'other')),
    location    VARCHAR(200),
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_active   BOOLEAN      NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE devices IS 'Registered data sources (ESP32 nodes, simulators)';

-- Insert default simulator device
INSERT INTO devices (device_id, name, type, location)
VALUES ('00000000-0000-0000-0000-000000000001', 'simulator-01', 'simulator', 'virtual')
ON CONFLICT DO NOTHING;

-- ── Measurements (AC load side) ───────────────────────────
CREATE TABLE IF NOT EXISTS measurements (
    id           BIGSERIAL    PRIMARY KEY,
    device_id    UUID         NOT NULL REFERENCES devices(device_id),
    timestamp    TIMESTAMPTZ  NOT NULL,
    voltage_v    REAL,
    current_a    REAL,
    power_w      REAL,
    energy_kwh   REAL,
    power_factor REAL,
    frequency_hz REAL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_measurements_ts
    ON measurements (timestamp);
CREATE INDEX IF NOT EXISTS idx_measurements_device_ts
    ON measurements (device_id, timestamp);

COMMENT ON TABLE measurements IS 'AC electrical measurements from building load meter';

-- ── PV Measurements ──────────────────────────────────────
CREATE TABLE IF NOT EXISTS pv_measurements (
    id            BIGSERIAL    PRIMARY KEY,
    device_id     UUID         NOT NULL REFERENCES devices(device_id),
    timestamp     TIMESTAMPTZ  NOT NULL,
    pv_voltage_v  REAL,
    pv_current_a  REAL,
    pv_power_w    REAL,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pv_ts
    ON pv_measurements (timestamp);
CREATE INDEX IF NOT EXISTS idx_pv_device_ts
    ON pv_measurements (device_id, timestamp);

COMMENT ON TABLE pv_measurements IS 'DC/AC measurements from PV system';

-- ── Battery Status ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS battery_status (
    id            BIGSERIAL    PRIMARY KEY,
    device_id     UUID         NOT NULL REFERENCES devices(device_id),
    timestamp     TIMESTAMPTZ  NOT NULL,
    voltage_v     REAL,
    current_a     REAL,        -- positive = charging, negative = discharging
    power_w       REAL,        -- positive = charging, negative = discharging
    soc_percent   REAL         CHECK (soc_percent >= 0 AND soc_percent <= 100),
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_battery_ts
    ON battery_status (timestamp);

COMMENT ON TABLE battery_status IS 'Battery voltage, current, power, and state of charge';

-- ── Environmental Data ───────────────────────────────────
CREATE TABLE IF NOT EXISTS environmental_data (
    id               BIGSERIAL    PRIMARY KEY,
    device_id        UUID         NOT NULL REFERENCES devices(device_id),
    timestamp        TIMESTAMPTZ  NOT NULL,
    temperature_c    REAL,
    humidity_percent REAL,
    irradiance_wm2   REAL,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_env_ts
    ON environmental_data (timestamp);

COMMENT ON TABLE environmental_data IS 'Ambient temperature, humidity, solar irradiance';

-- ── Energy Flows (aggregated per time step) ──────────────
CREATE TABLE IF NOT EXISTS energy_flows (
    id                BIGSERIAL    PRIMARY KEY,
    device_id         UUID         NOT NULL REFERENCES devices(device_id),
    timestamp         TIMESTAMPTZ  NOT NULL,
    pv_power_w        REAL,
    load_power_w      REAL,
    grid_power_w      REAL,        -- positive = import, negative = export
    battery_power_w   REAL,        -- positive = charging, negative = discharging
    pv_to_load_w      REAL,
    pv_to_battery_w   REAL,
    battery_to_load_w REAL,
    pv_curtailed_w    REAL,
    soc_percent       REAL,
    data_source       VARCHAR(20)  DEFAULT 'real' CHECK (data_source IN ('real', 'synthetic')),
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_flows_ts
    ON energy_flows (timestamp);
CREATE INDEX IF NOT EXISTS idx_flows_device_ts
    ON energy_flows (device_id, timestamp);

COMMENT ON TABLE energy_flows IS 'Consolidated energy flow snapshot per time step';

-- ── Predictions ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS predictions (
    id                BIGSERIAL    PRIMARY KEY,
    timestamp         TIMESTAMPTZ  NOT NULL,   -- prediction target time
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    prediction_type   VARCHAR(30)  NOT NULL CHECK (prediction_type IN ('consumption', 'pv')),
    model_name        VARCHAR(50)  NOT NULL,
    predicted_value_w REAL         NOT NULL,
    actual_value_w    REAL                      -- filled after the fact
);

CREATE INDEX IF NOT EXISTS idx_pred_ts_type
    ON predictions (timestamp, prediction_type);

COMMENT ON TABLE predictions IS 'ML model predictions and corresponding actuals';

-- ── Optimization Results ─────────────────────────────────
CREATE TABLE IF NOT EXISTS optimization_results (
    id                 BIGSERIAL    PRIMARY KEY,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    horizon_start      TIMESTAMPTZ  NOT NULL,
    horizon_end        TIMESTAMPTZ  NOT NULL,
    strategy           VARCHAR(20)  NOT NULL CHECK (strategy IN ('rule_based', 'milp')),
    schedule_json      JSONB        NOT NULL,
    expected_cost_mad  REAL,
    expected_grid_kwh  REAL,
    actual_cost_mad    REAL,        -- filled after execution
    actual_grid_kwh    REAL
);

CREATE INDEX IF NOT EXISTS idx_opt_created
    ON optimization_results (created_at);

COMMENT ON TABLE optimization_results IS 'EMS dispatch schedules and cost projections';

-- ── Alerts ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alerts (
    id            BIGSERIAL    PRIMARY KEY,
    timestamp     TIMESTAMPTZ  NOT NULL,
    alert_type    VARCHAR(50)  NOT NULL,
    severity      VARCHAR(10)  NOT NULL CHECK (severity IN ('info', 'warning', 'critical')),
    message       TEXT         NOT NULL,
    details_json  JSONB,
    acknowledged  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alerts_ts_sev
    ON alerts (timestamp, severity);

COMMENT ON TABLE alerts IS 'Anomaly detection alerts and system warnings';

-- ── Daily Performance Summary ────────────────────────────
CREATE TABLE IF NOT EXISTS daily_performance (
    id                    BIGSERIAL    PRIMARY KEY,
    date                  DATE         NOT NULL UNIQUE,
    strategy              VARCHAR(20)  NOT NULL,
    pv_generation_kwh     REAL,
    load_consumption_kwh  REAL,
    grid_import_kwh       REAL,
    grid_export_kwh       REAL         DEFAULT 0,
    battery_charge_kwh    REAL,
    battery_discharge_kwh REAL,
    self_consumption_pct  REAL,
    self_sufficiency_pct  REAL,
    peak_demand_w         REAL,
    energy_cost_mad       REAL,
    co2_avoided_kg        REAL,
    created_at            TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_date
    ON daily_performance (date);

COMMENT ON TABLE daily_performance IS 'Daily aggregated performance metrics for comparison';
