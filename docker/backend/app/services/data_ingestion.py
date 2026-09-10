"""
Bulk data ingestion — loads synthetic CSV data into the database.

Usage:
    python -m backend.app.services.data_ingestion --csv ml/data/raw/synthetic_90d.csv
"""

import argparse
import logging

import pandas as pd
from sqlalchemy.orm import Session

from ..database import get_engine, get_session_factory, init_db
from ..models import (
    BatteryStatus, Device, EnvironmentalData, EnergyFlow,
    Measurement, PVMeasurement,
)

logger = logging.getLogger(__name__)

SIMULATOR_DEVICE_ID = "00000000-0000-0000-0000-000000000001"
BATCH_SIZE = 500


def load_csv_to_db(csv_path: str):
    """
    Read a synthetic CSV and insert all rows into the database tables.
    """
    # Ensure tables exist
    init_db()

    df = pd.read_csv(csv_path, parse_dates=["timestamp"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    logger.info(f"Loaded {len(df)} rows from {csv_path}")

    factory = get_session_factory()
    session: Session = factory()

    try:
        # Ensure simulator device exists
        device = session.query(Device).filter(
            Device.device_id == SIMULATOR_DEVICE_ID
        ).first()
        if not device:
            session.add(Device(
                device_id=SIMULATOR_DEVICE_ID,
                name="simulator-01",
                type="simulator",
                location="virtual",
            ))
            session.commit()

        inserted = 0
        for start in range(0, len(df), BATCH_SIZE):
            batch = df.iloc[start:start + BATCH_SIZE]
            objects = []

            for _, row in batch.iterrows():
                ts = row["timestamp"].to_pydatetime()

                objects.append(Measurement(
                    device_id=SIMULATOR_DEVICE_ID,
                    timestamp=ts,
                    voltage_v=230.0,
                    current_a=round(row.get("load_power_w", 0) / 230.0, 2),
                    power_w=row.get("load_power_w"),
                    energy_kwh=row.get("load_energy_kwh"),
                    power_factor=0.95,
                    frequency_hz=50.0,
                ))

                objects.append(PVMeasurement(
                    device_id=SIMULATOR_DEVICE_ID,
                    timestamp=ts,
                    pv_voltage_v=row.get("pv_voltage_v"),
                    pv_current_a=row.get("pv_current_a"),
                    pv_power_w=row.get("pv_power_w"),
                ))

                objects.append(BatteryStatus(
                    device_id=SIMULATOR_DEVICE_ID,
                    timestamp=ts,
                    voltage_v=row.get("battery_voltage_v"),
                    current_a=row.get("battery_current_a"),
                    power_w=row.get("battery_power_w"),
                    soc_percent=row.get("soc_pct"),
                ))

                objects.append(EnvironmentalData(
                    device_id=SIMULATOR_DEVICE_ID,
                    timestamp=ts,
                    temperature_c=row.get("temperature_c"),
                    humidity_percent=row.get("humidity_pct"),
                    irradiance_wm2=row.get("irradiance_wm2"),
                ))

                objects.append(EnergyFlow(
                    device_id=SIMULATOR_DEVICE_ID,
                    timestamp=ts,
                    pv_power_w=row.get("pv_power_w"),
                    load_power_w=row.get("load_power_w"),
                    grid_power_w=row.get("grid_power_w"),
                    battery_power_w=row.get("battery_power_w"),
                    pv_to_load_w=row.get("pv_to_load_w"),
                    pv_to_battery_w=row.get("pv_to_battery_w"),
                    battery_to_load_w=row.get("battery_to_load_w"),
                    pv_curtailed_w=row.get("pv_curtailed_w"),
                    soc_percent=row.get("soc_pct"),
                    data_source="synthetic",
                ))

            session.bulk_save_objects(objects)
            session.commit()
            inserted += len(batch)
            logger.info(f"Inserted {inserted}/{len(df)} rows")

        logger.info(f"Ingestion complete: {inserted} time steps → 5 tables")

    except Exception as e:
        session.rollback()
        logger.error(f"Ingestion failed: {e}")
        raise
    finally:
        session.close()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="Load synthetic CSV into database")
    parser.add_argument("--csv", required=True, help="Path to synthetic CSV file")
    args = parser.parse_args()

    load_csv_to_db(args.csv)


if __name__ == "__main__":
    main()
