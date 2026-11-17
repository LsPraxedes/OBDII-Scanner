
from datetime import datetime
from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import backend.main
from backend.config import TEST_DATABASE_URL
from backend.database import Base, Telemetry, get_db
from backend.main import app

SQLALCHEMY_DATABASE_URL = TEST_DATABASE_URL
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

# Mocking the MQTT client for tests
mock_mqtt_client = MagicMock()
backend.main.get_mqtt_client = lambda: mock_mqtt_client

client = TestClient(app)

def test_create_telemetry():
    """
    Testa a criação de um registro de telemetria válido.
    """
    response = client.post(
        "/api/v1/telemetry",
        json={"rpm": 3000.5, "temperature": 90.0, "speed": 100.0},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["rpm"] == 3000.5
    assert "id" in data

def test_create_telemetry_invalid():
    """
    Testa a rejeição de dados inválidos pelo Pydantic.
    """
    response = client.post(
        "/api/v1/telemetry",
        json={"rpm": "not_a_number", "temperature": 90.0},
    )
    assert response.status_code == 422

def test_read_telemetry():
    """
    Testa a leitura do histórico de telemetria.
    """
    response = client.get("/api/v1/telemetry")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_read_telemetry_time_filter_and_days_summary():
    """
    Testa filtros temporais (start_time/end_time com fuso) e resumo diário /days.
    """
    db = TestingSessionLocal()
    inserted_ids = []
    try:
        # 01:30 UTC de 11/05 corresponde a 22:30 BRT (UTC-3) do dia 10/05
        samples = [
            Telemetry(
                rpm=1100.0,
                temperature=82.0,
                speed=15.0,
                timestamp=datetime(2025, 5, 11, 1, 30, 0),
            ),
            Telemetry(
                rpm=2200.0,
                temperature=87.0,
                speed=45.0,
                timestamp=datetime(2025, 5, 11, 1, 30, 5),
            ),
        ]
        db.add_all(samples)
        db.commit()
        for row in samples:
            db.refresh(row)
            inserted_ids.append(row.id)

        filtered = client.get(
            "/api/v1/telemetry",
            params={
                "start_time": "2025-05-10T22:00:00-03:00",
                "end_time": "2025-05-10T23:00:00-03:00",
                "limit": 500,
            },
        )
        assert filtered.status_code == 200
        items = filtered.json()
        assert len(items) == 2
        assert items[0]["rpm"] == 2200.0

        days_resp = client.get("/api/v1/telemetry/days", params={"tz_offset_minutes": -180})
        assert days_resp.status_code == 200
        days_list = days_resp.json()
        matching = [d for d in days_list if d["date"] == "2025-05-10"]
        assert len(matching) == 1
        assert matching[0]["count"] == 2
    finally:
        if inserted_ids:
            db.query(Telemetry).filter(Telemetry.id.in_(inserted_ids)).delete(
                synchronize_session=False
            )
            db.commit()
        db.close()
