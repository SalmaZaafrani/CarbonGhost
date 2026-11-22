"""
Container du service mesures : app FastAPI, middlewares, exception
handlers, health check, router, et assemblage des dépendances.
"""
import os
from contextlib import contextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.rest.mesures_router import router as mesures_router
from application.use_cases.ProcessMeasurementUseCase import ProcessMeasurementUseCase
from domain.exceptions.base_exceptions import (
    DomainException,
    NotFoundException,
    ValidationException,
    ConflictException,
    UnauthorizedException,
)
from infrastructure.persistence.postgres.models import Base
from infrastructure.persistence.postgres.postgres_measurement_repository import (
    PostgresMeasurementRepository,
)
from infrastructure.kafka.kafka_measurement_publisher import KafkaMeasurementPublisher
from infrastructure.mqtt.mqtt_client import start_mqtt_listener

SERVICE_NAME = "mesures"

app = FastAPI(title="service-mesures")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATUS_BY_EXCEPTION = {
    NotFoundException: 404,
    ValidationException: 422,
    ConflictException: 409,
    UnauthorizedException: 401,
}


@app.exception_handler(DomainException)
def handle_domain_exception(request: Request, exc: DomainException):
    return JSONResponse(status_code=_STATUS_BY_EXCEPTION.get(type(exc), 400), content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE_NAME}


app.include_router(mesures_router)


# --- Configuration technique ---------------------------------------------

DATABASE_URL = os.environ["DATABASE_URL"]
KAFKA_BROKER = os.environ["KAFKA_BROKER"]
MQTT_BROKER = os.environ["MQTT_BROKER"]
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

# Le publisher Kafka est unique pour toute la durée de vie du service.
publisher = KafkaMeasurementPublisher(broker_address=KAFKA_BROKER)


@contextmanager
def get_process_measurement_use_case():
    """
    Fournit un ProcessMeasurementUseCase avec sa propre session SQLAlchemy,
    utilisé par le listener MQTT (infrastructure/mqtt/mqtt_client.py).
    """
    session = SessionLocal()
    try:
        repository = PostgresMeasurementRepository(session)
        yield ProcessMeasurementUseCase(repository=repository, publisher=publisher)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_measurement_repository():
    """Utilisé par api/rest/mesures_router.py pour les lectures seules."""
    session = SessionLocal()
    try:
        yield PostgresMeasurementRepository(session)
    finally:
        session.close()


# --- Cycle de vie ----------------------------------------------------------

mqtt_client = None


@app.on_event("startup")
def on_startup():
    global mqtt_client
    Base.metadata.create_all(engine)  # crée la table "mesures" si elle n'existe pas
    mqtt_client = start_mqtt_listener(broker_address=MQTT_BROKER, broker_port=MQTT_PORT)


@app.on_event("shutdown")
def on_shutdown():
    if mqtt_client is not None:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
