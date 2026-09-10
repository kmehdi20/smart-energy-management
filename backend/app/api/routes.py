"""
REST API endpoints for the Smart Energy Management System.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, text
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import get_settings
from ..models import (
    Alert, DailyPerformance, Device, EnergyFlow, Prediction,
)
from ..schemas import (
    AlertOut, DailyPerformanceOut, DeviceOut,
    EnergyFlowOut, HealthResponse, PredictionOut,
)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """Check database and MQTT connectivity."""
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    settings = get_settings()
    if settings.mqtt_enabled:
        from ..services.mqtt_subscriber import get_mqtt_subscriber
        mqtt_sub = get_mqtt_subscriber()
        mqtt_status = "connected" if mqtt_sub.is_connected else "disconnected"
    else:
        mqtt_status = "disabled"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        mqtt=mqtt_status,
    )


@router.get("/devices", response_model=list[DeviceOut])
def list_devices(db: Session = Depends(get_db)):
    return db.query(Device).filter(Device.is_active == True).all()


@router.get("/energy-flows", response_model=list[EnergyFlowOut])
def get_energy_flows(
    start: Optional[datetime] = Query(None),
    end: Optional[datetime] = Query(None),
    limit: int = Query(96, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    query = db.query(EnergyFlow)
    if start:
        query = query.filter(EnergyFlow.timestamp >= start)
    if end:
        query = query.filter(EnergyFlow.timestamp <= end)
    return query.order_by(desc(EnergyFlow.timestamp)).limit(limit).all()


@router.get("/energy-flows/latest", response_model=EnergyFlowOut | None)
def get_latest_energy_flow(db: Session = Depends(get_db)):
    return db.query(EnergyFlow).order_by(desc(EnergyFlow.timestamp)).first()


@router.get("/alerts", response_model=list[AlertOut])
def get_alerts(
    severity: Optional[str] = Query(None),
    acknowledged: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(Alert)
    if severity:
        query = query.filter(Alert.severity == severity)
    if acknowledged is not None:
        query = query.filter(Alert.acknowledged == acknowledged)
    return query.order_by(desc(Alert.timestamp)).limit(limit).all()


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        return {"error": "Alert not found"}
    alert.acknowledged = True
    db.commit()
    return {"status": "acknowledged", "id": alert_id}


@router.get("/predictions", response_model=list[PredictionOut])
def get_predictions(
    prediction_type: Optional[str] = Query(None),
    limit: int = Query(96, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    query = db.query(Prediction)
    if prediction_type:
        query = query.filter(Prediction.prediction_type == prediction_type)
    return query.order_by(desc(Prediction.timestamp)).limit(limit).all()


@router.get("/performance", response_model=list[DailyPerformanceOut])
def get_performance(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    return (
        db.query(DailyPerformance)
        .filter(DailyPerformance.date >= cutoff.date())
        .order_by(DailyPerformance.date)
        .all()
    )
