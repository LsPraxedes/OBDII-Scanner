from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

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

    model_config = ConfigDict(from_attributes=True)


class TelemetryDaySummary(BaseModel):
    """
    Schema com o resumo diário de registros disponíveis no banco de telemetria.
    """
    date: date
    count: int
    first_timestamp: datetime
    last_timestamp: datetime

    model_config = ConfigDict(from_attributes=True)
