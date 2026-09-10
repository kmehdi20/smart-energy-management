"""
Application configuration — loaded from environment variables / .env file.

Defaults to SQLite for local development (no Docker required).
Switch to PostgreSQL by setting DATABASE_URL in .env.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

# Project root (3 levels up from this file: backend/app/config.py → project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """All application settings, sourced from environment variables."""

    # Database — defaults to SQLite (no Docker needed)
    database_url: str = f"sqlite:///{_PROJECT_ROOT / 'data' / 'smart_energy.db'}"

    # MQTT (optional — backend works without it)
    mqtt_broker_host: str = "localhost"
    mqtt_broker_port: int = 1883
    mqtt_username: str = "energy_mqtt"
    mqtt_password: str = "change_me_in_production"
    mqtt_client_id: str = "backend-subscriber"
    mqtt_topic_prefix: str = "building"
    mqtt_enabled: bool = False  # set True when broker is running

    # FastAPI
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = True

    # General
    timezone: str = "Africa/Casablanca"
    log_level: str = "INFO"

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
