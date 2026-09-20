from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import logging

from backend import database
from backend.schemas.telemetry import TelemetryCreate, TelemetryResponse

# Configuração de log
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar as tabelas no banco de dados SQLite
database.Base.metadata.create_all(bind=database.engine)

app = FastAPI(
    title="Central de Análise Veicular Preditiva",
    description="API for validating and storing OBD-II telemetry data",
    version="0.0.1"
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
def read_telemetry(skip: int = 0, limit: int = 100, db: Session = Depends(database.get_db)):
    """
    Endpoint para listar os dados de telemetria salvos.
    """
    try:
        telemetries = db.query(database.Telemetry).order_by(database.Telemetry.timestamp.desc()).offset(skip).limit(limit).all()
        return telemetries
    except Exception as e:
        logger.error(f"Failed to read telemetry: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
