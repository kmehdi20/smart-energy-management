"""
MQTT subscriber service.

Connects to the Mosquitto broker, subscribes to telemetry topics,
validates payloads via Pydantic, and inserts data into PostgreSQL.
"""

import json
import logging
import threading
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session_factory
from ..models import (
    BatteryStatus, Device, EnvironmentalData, EnergyFlow,
    Measurement, PVMeasurement,
)
from ..schemas import TelemetryPayload

logger = logging.getLogger(__name__)


class MQTTSubscriber:
    """
    Manages MQTT connection and data ingestion into the database.

    Subscribes to:
        {prefix}/+/telemetry    — bundled telemetry payloads
        {prefix}/+/status       — device heartbeats
    """

    def __init__(self):
        self.settings = get_settings()
        self.client = mqtt.Client(
            client_id=self.settings.mqtt_client_id,
            protocol=mqtt.MQTTv311,
        )
        self.client.username_pw_set(
            self.settings.mqtt_username,
            self.settings.mqtt_password,
        )
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)

        self._session_factory = get_session_factory()
        self._running = False

    def start(self):
        """Connect to broker and start the network loop in a background thread."""
        logger.info(
            f"Connecting to MQTT broker at "
            f"{self.settings.mqtt_broker_host}:{self.settings.mqtt_broker_port}"
        )
        try:
            self.client.connect(
                self.settings.mqtt_broker_host,
                self.settings.mqtt_broker_port,
                keepalive=60,
            )
            self._running = True
            self.client.loop_start()
            logger.info("MQTT subscriber started (background thread)")
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            logger.warning("Backend will continue without MQTT — use API for data ingestion")

    def stop(self):
        """Disconnect and stop the background loop."""
        self._running = False
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT subscriber stopped")

    @property
    def is_connected(self) -> bool:
        return self.client.is_connected()

    # ── MQTT Callbacks ────────────────────────────────────

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker")
            prefix = self.settings.mqtt_topic_prefix
            client.subscribe(f"{prefix}/+/telemetry", qos=0)
            client.subscribe(f"{prefix}/+/status", qos=0)
            logger.info(f"Subscribed to {prefix}/+/telemetry and {prefix}/+/status")
        else:
            logger.error(f"MQTT connection refused, code={rc}")

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning(f"MQTT disconnected unexpectedly (rc={rc}), will reconnect")
        else:
            logger.info("MQTT disconnected cleanly")

    def _on_message(self, client, userdata, msg):
        """Process incoming MQTT message."""
        try:
            topic = msg.topic
            payload_str = msg.payload.decode("utf-8")

            if topic.endswith("/status"):
                logger.debug(f"Heartbeat from {topic}: {payload_str}")
                return

            if topic.endswith("/telemetry"):
                self._process_telemetry(payload_str)

        except Exception as e:
            logger.error(f"Error processing MQTT message on {msg.topic}: {e}")

    # ── Data Processing ───────────────────────────────────

    def _process_telemetry(self, payload_str: str):
        """Parse, validate, and store a telemetry payload."""
        try:
            raw = json.loads(payload_str)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON payload: {e}")
            return

        try:
            telemetry = TelemetryPayload(**raw)
        except Exception as e:
            logger.warning(f"Payload validation failed: {e}")
            return

        session: Session = self._session_factory()
        try:
            device_id = self._ensure_device(session, telemetry.device_id)
            ts = telemetry.timestamp

            # Insert load measurement
            if telemetry.load:
                session.add(Measurement(
                    device_id=device_id,
                    timestamp=ts,
                    voltage_v=telemetry.load.voltage_v,
                    current_a=telemetry.load.current_a,
                    power_w=telemetry.load.power_w,
                    energy_kwh=telemetry.load.energy_kwh,
                    power_factor=telemetry.load.pf,
                    frequency_hz=telemetry.load.freq_hz,
                ))

            # Insert PV measurement
            if telemetry.pv:
                session.add(PVMeasurement(
                    device_id=device_id,
                    timestamp=ts,
                    pv_voltage_v=telemetry.pv.voltage_v,
                    pv_current_a=telemetry.pv.current_a,
                    pv_power_w=telemetry.pv.power_w,
                ))

            # Insert battery status
            if telemetry.battery:
                bat_power = telemetry.battery.voltage_v * telemetry.battery.current_a
                session.add(BatteryStatus(
                    device_id=device_id,
                    timestamp=ts,
                    voltage_v=telemetry.battery.voltage_v,
                    current_a=telemetry.battery.current_a,
                    power_w=bat_power,
                    soc_percent=telemetry.battery.soc_pct,
                ))

            # Insert environmental data
            if telemetry.env:
                session.add(EnvironmentalData(
                    device_id=device_id,
                    timestamp=ts,
                    temperature_c=telemetry.env.temperature_c,
                    humidity_percent=telemetry.env.humidity_pct,
                    irradiance_wm2=telemetry.env.irradiance_wm2,
                ))

            # Insert consolidated energy flow
            session.add(EnergyFlow(
                device_id=device_id,
                timestamp=ts,
                pv_power_w=telemetry.pv.power_w if telemetry.pv else None,
                load_power_w=telemetry.load.power_w if telemetry.load else None,
                grid_power_w=None,  # computed later by optimization
                battery_power_w=(
                    telemetry.battery.voltage_v * telemetry.battery.current_a
                    if telemetry.battery else None
                ),
                soc_percent=telemetry.battery.soc_pct if telemetry.battery else None,
                data_source="real",
            ))

            session.commit()
            logger.debug(f"Stored telemetry from {telemetry.device_id} at {ts}")

        except Exception as e:
            session.rollback()
            logger.error(f"Database insert failed: {e}")
        finally:
            session.close()

    def _ensure_device(self, session: Session, device_name: str):
        """Get or create a device record. Returns device_id (UUID)."""
        device = session.query(Device).filter(Device.name == device_name).first()
        if device:
            return device.device_id

        device = Device(
            name=device_name,
            type="esp32" if "esp32" in device_name.lower() else "simulator",
            location="auto-registered",
        )
        session.add(device)
        session.flush()
        logger.info(f"Auto-registered device: {device_name} ({device.device_id})")
        return device.device_id


# Module-level singleton
_subscriber: MQTTSubscriber | None = None


def get_mqtt_subscriber() -> MQTTSubscriber:
    global _subscriber
    if _subscriber is None:
        _subscriber = MQTTSubscriber()
    return _subscriber
