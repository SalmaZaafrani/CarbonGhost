"""
Container du service factory : app FastAPI, middlewares, exception
handlers, health check, router, et assemblage des dépendances.
"""
import os
from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.rest.factory_router import router as factory_router
from application.use_cases.machine_use_cases import (
    CreateMachineUseCase, DeleteMachineUseCase, GetMachineUseCase, ListMachinesUseCase, UpdateMachineUseCase,
)
from domain.entities.machine import Machine
from domain.exceptions.exception import (
    ConflictException, DomainException, NotFoundException, UnauthorizedException, ValidationException,
)
from infrastructure.persistence.postgres.models import Base
from infrastructure.persistence.postgres.postgres_machine_repository import PostgresMachineRepository

SERVICE_NAME = "factory"

app = FastAPI(title="service-factory")

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


app.include_router(factory_router)


# --- Configuration technique ---------------------------------------------

DATABASE_URL = os.environ["DATABASE_URL"]
SEED_DEMO_MACHINES = os.environ.get("SEED_DEMO_MACHINES", "1") == "1"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

# Machines de démonstration (mêmes identifiants que le simulateur de capteurs)
DEMO_MACHINES = [
    Machine(id="M1", name="Presse hydraulique", production_line="Ligne A", location="Atelier 1",
            machine_type="presse", nominal_power_kw=4.0, expected_kwh_per_unit=0.1),
    Machine(id="M2", name="Compresseur d'air", production_line="Ligne A", location="Atelier 1",
            machine_type="compresseur", nominal_power_kw=3.5, expected_kwh_per_unit=0.1),
    Machine(id="M3", name="Convoyeur principal", production_line="Ligne B", location="Atelier 2",
            machine_type="convoyeur", nominal_power_kw=2.5, expected_kwh_per_unit=0.1),
    Machine(id="M4", name="Tour CNC", production_line="Ligne B", location="Atelier 2",
            machine_type="usinage", nominal_power_kw=5.0, expected_kwh_per_unit=0.1),
]


@contextmanager
def use_cases():
    session = SessionLocal()
    try:
        repo = PostgresMachineRepository(session)
        yield SimpleNamespace(
            create=CreateMachineUseCase(repo),
            update=UpdateMachineUseCase(repo),
            get=GetMachineUseCase(repo),
            list=ListMachinesUseCase(repo),
            delete=DeleteMachineUseCase(repo),
        )
    finally:
        session.close()


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(engine)  # crée la table "machines" si elle n'existe pas
    if SEED_DEMO_MACHINES:
        with SessionLocal() as session:
            repo = PostgresMachineRepository(session)
            if not repo.find_all():
                for machine in DEMO_MACHINES:
                    repo.save(machine)
