
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import MagicMock
import backend.main

from backend.main import app
from backend.database import Base, get_db
from backend.config import TEST_DATABASE_URL

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
