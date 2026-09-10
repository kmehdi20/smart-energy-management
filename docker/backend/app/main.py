"""
FastAPI application entry point.

Starts the REST API server and optionally the MQTT subscriber.

Usage:
    uvicorn backend.app.main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router
from .config import get_settings
from .database import check_connection, init_db
from .utils import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    setup_logging()
    settings = get_settings()
    logger.info("Starting Smart Energy Management Backend")
    logger.info(f"Database: {settings.database_url.split('://')[0]}")

    # Initialize database (create tables if needed)
    init_db()

    # Check database
    if check_connection():
        logger.info("Database connection verified")
    else:
        logger.warning("Database unavailable — API will return errors for DB queries")

    # Start MQTT subscriber only if enabled
    mqtt_sub = None
    if settings.mqtt_enabled:
        from .services.mqtt_subscriber import get_mqtt_subscriber
        mqtt_sub = get_mqtt_subscriber()
        mqtt_sub.start()
    else:
        logger.info("MQTT disabled (set MQTT_ENABLED=true in .env to enable)")

    yield

    # Shutdown
    logger.info("Shutting down")
    if mqtt_sub:
        mqtt_sub.stop()


app = FastAPI(
    title="Smart Energy Management API",
    description="REST API for the AI-Based Smart Energy Management System",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow dashboard (Streamlit) and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(router, prefix="/api/v1")


@app.get("/")
def root():
    return {
        "name": "Smart Energy Management API",
        "version": "0.1.0",
        "docs": "/docs",
    }
