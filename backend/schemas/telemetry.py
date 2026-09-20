from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional

class TelemetryCreate(BaseModel):
    """
    Schema para validar dados de telemetria recebidos (Pydantic).
    """
    rpm: float = Field(..., description="Engine RPM")
    temperature: float = Field(..., description="Engine Coolant Temperature in Celsius")
    speed: Optional[float] = Field(None, description="Vehicle speed in km/h")

class TelemetryResponse(TelemetryCreate):
    """
    Schema para retorno de dados de telemetria salvos.
    """
    id: int
    timestamp: datetime

    class Config:
        from_attributes = True
