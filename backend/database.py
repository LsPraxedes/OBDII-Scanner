from sqlalchemy import create_engine, Column, Integer, Float, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime, timezone

SQLALCHEMY_DATABASE_URL = "sqlite:///./vehicle_data.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Telemetry(Base):
    """
    Modelo ORM representando a tabela de telemetria no SQLite.
    """
    __tablename__ = "telemetry"

    id = Column(Integer, primary_key=True, index=True)
    rpm = Column(Float, nullable=False)
    temperature = Column(Float, nullable=False)
    speed = Column(Float, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

def get_db():
    """
    Injeção de dependência para obter a sessão do banco.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
