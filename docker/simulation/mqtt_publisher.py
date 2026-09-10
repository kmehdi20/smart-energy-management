"""
MQTT publisher for simulation data.

Reads a synthetic CSV and publishes rows as MQTT telemetry messages,
simulating an ESP32 sending data. Useful for integration testing
the full pipeline: MQTT → Backend → Database.

Usage:
    python -m simulation.mqtt_publisher --csv ml/data/raw/test_sunny_7d.csv --rate 10
"""

import argparse
import json
import logging
import time

import pandas as pd
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def publish_dataset(
    csv_path: str,
    broker_host: str = "localhost",
    broker_port: int = 1883,
    username: str = "energy_mqtt",
    password: str = "change_me_in_production",
    topic_prefix: str = "building",
    device_id: str = "simulator-01",
    rate: float = 10.0,
):
    """
    Publish each row of a CSV as an MQTT telemetry message.

    Parameters
    ----------
    csv_path : str
        Path to synthetic CSV.
    rate : float
        Messages per second (default 10 = ~100ms between messages).
    """
    df = pd.read_csv(csv_path)
    logger.info(f"Loaded {len(df)} rows from {csv_path}")

    client = mqtt.Client(client_id="sim-publisher", protocol=mqtt.MQTTv311)
    client.username_pw_set(username, password)

    logger.info(f"Connecting to MQTT broker at {broker_host}:{broker_port}")
    client.connect(broker_host, broker_port, keepalive=60)
    client.loop_start()

    topic = f"{topic_prefix}/{device_id}/telemetry"
    delay = 1.0 / rate
    published = 0

    try:
        for _, row in df.iterrows():
            payload = {
                "timestamp": row["timestamp"],
                "device_id": device_id,
                "load": {
                    "voltage_v": 230.0,
                    "current_a": round(row.get("load_power_w", 0) / 230.0, 2),
                    "power_w": row.get("load_power_w", 0),
                    "energy_kwh": row.get("load_energy_kwh", 0),
                    "pf": 0.95,
                    "freq_hz": 50.0,
                },
                "pv": {
                    "voltage_v": row.get("pv_voltage_v", 0),
                    "current_a": row.get("pv_current_a", 0),
                    "power_w": row.get("pv_power_w", 0),
                },
                "battery": {
                    "voltage_v": row.get("battery_voltage_v", 48.0),
                    "current_a": row.get("battery_current_a", 0),
                    "soc_pct": row.get("soc_pct", 50.0),
                },
                "env": {
                    "temperature_c": row.get("temperature_c", 25.0),
                    "humidity_pct": row.get("humidity_pct", 50.0),
                    "irradiance_wm2": row.get("irradiance_wm2", 0),
                },
            }

            client.publish(topic, json.dumps(payload), qos=0)
            published += 1

            if published % 100 == 0:
                logger.info(f"Published {published}/{len(df)} messages")

            time.sleep(delay)

    except KeyboardInterrupt:
        logger.info("Stopped by user")
    finally:
        client.loop_stop()
        client.disconnect()
        logger.info(f"Done: published {published} messages to {topic}")


def main():
    parser = argparse.ArgumentParser(description="Publish synthetic data via MQTT")
    parser.add_argument("--csv", required=True, help="Path to synthetic CSV")
    parser.add_argument("--host", default="localhost", help="MQTT broker host")
    parser.add_argument("--port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--username", default="energy_mqtt")
    parser.add_argument("--password", default="change_me_in_production")
    parser.add_argument("--rate", type=float, default=10.0, help="Messages per second")
    args = parser.parse_args()

    publish_dataset(
        csv_path=args.csv,
        broker_host=args.host,
        broker_port=args.port,
        username=args.username,
        password=args.password,
        rate=args.rate,
    )


if __name__ == "__main__":
    main()
