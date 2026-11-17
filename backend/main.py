from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend import database
from backend.config import MQTT_BROKER, MQTT_PORT
from backend.mqtt_client import get_mqtt_client
from backend.schemas.telemetry import (
    TelemetryCreate,
    TelemetryDaySummary,
    TelemetryResponse,
)

# Configuração de log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar as tabelas no banco de dados SQLite e garantir índice temporal
database.Base.metadata.create_all(bind=database.engine)
with database.engine.begin() as conn:
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_telemetry_timestamp ON telemetry (timestamp)"))


def normalize_to_naive_utc(dt: datetime) -> datetime:
    """
    Normaliza um datetime (com ou sem fuso horário) para UTC ingênuo compatível com SQLite.
    """
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize MQTT Client
    client = get_mqtt_client()
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        logger.info("MQTT Client loop started in background.")
    except Exception as e:
        logger.error(f"Could not connect to MQTT Broker at startup: {e}")
    
    yield
    
    # Shutdown: Stop MQTT Client
    client.loop_stop()
    client.disconnect()
    logger.info("MQTT Client disconnected.")

app = FastAPI(
    title="Central de Análise Veicular Preditiva",
    description="API for validating and storing OBD-II telemetry data",
    version="0.0.1",
    lifespan=lifespan
)

@app.post("/api/v1/telemetry", response_model=TelemetryResponse)
def create_telemetry(telemetry: TelemetryCreate, db: Session = Depends(database.get_db)):
    """
    Endpoint para receber e salvar dados de telemetria.
    """
    try:
        db_telemetry = database.Telemetry(**telemetry.model_dump())
        db.add(db_telemetry)
        db.commit()
        db.refresh(db_telemetry)
        logger.info(f"Telemetry saved: id={db_telemetry.id}")
        return db_telemetry
    except Exception as e:
        logger.error(f"Failed to save telemetry: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/api/v1/telemetry", response_model=List[TelemetryResponse])
def read_telemetry(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=50000),
    start_time: Optional[datetime] = Query(default=None),
    end_time: Optional[datetime] = Query(default=None),
    db: Session = Depends(database.get_db),
):
    """
    Endpoint para listar os dados de telemetria salvos, com suporte opcional a janela temporal.
    """
    try:
        query = db.query(database.Telemetry)
        if start_time is not None:
            query = query.filter(database.Telemetry.timestamp >= normalize_to_naive_utc(start_time))
        if end_time is not None:
            query = query.filter(database.Telemetry.timestamp <= normalize_to_naive_utc(end_time))

        telemetries = (
            query.order_by(database.Telemetry.timestamp.desc(), database.Telemetry.id.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        return telemetries
    except Exception as e:
        logger.error(f"Failed to read telemetry: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/api/v1/telemetry/days", response_model=List[TelemetryDaySummary])
def read_telemetry_days(
    tz_offset_minutes: int = Query(default=-180, ge=-720, le=840),
    db: Session = Depends(database.get_db),
):
    """
    Lista os dias disponíveis no histórico com contagem de amostras e limites temporais.
    """
    try:
        offset_modifier = f"{tz_offset_minutes:+d} minutes"
        local_day_expr = func.date(database.Telemetry.timestamp, offset_modifier)
        rows = (
            db.query(
                local_day_expr.label("day"),
                func.count(database.Telemetry.id).label("total_count"),
                func.min(database.Telemetry.timestamp).label("first_ts"),
                func.max(database.Telemetry.timestamp).label("last_ts"),
            )
            .group_by(local_day_expr)
            .order_by(local_day_expr.desc())
            .all()
        )
        return [
            TelemetryDaySummary(
                date=row.day,
                count=row.total_count,
                first_timestamp=row.first_ts,
                last_timestamp=row.last_ts,
            )
            for row in rows
            if row.day is not None
        ]
    except Exception as e:
        logger.error(f"Failed to summarize telemetry days: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
