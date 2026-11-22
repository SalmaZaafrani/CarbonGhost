"""
Container du service user : app FastAPI, middlewares, exception handlers,
health check, router, et assemblage des dépendances.
"""
import os
from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.rest.user_router import router as user_router
from application.use_cases.userUseCases import (
    GetCurrentUserUseCase, ListUsersUseCase, LoginUseCase, RegisterUserUseCase, SetUserActiveUseCase,
)
from domain.entities.authorization import UserRole
from domain.entities.user import User
from domain.exceptions.exception import (
    AuthenticationFailedException, DomainException, ForbiddenException,
    UserAlreadyExistsException, UserInactiveException, UserNotFoundException,
)
from infrastructure.notifications.console_email_service import ConsoleEmailNotificationService
from infrastructure.persistence.postgres.models import Base
from infrastructure.persistence.postgres.postgres_user_repository import PostgresUserRepository
from infrastructure.security.jwt_token_service import JwtTokenService
from infrastructure.security.pbkdf2_hashing_service import Pbkdf2HashingService

SERVICE_NAME = "user"

app = FastAPI(title="service-user")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_STATUS_BY_EXCEPTION = {
    UserNotFoundException: 404,
    UserAlreadyExistsException: 409,
    AuthenticationFailedException: 401,
    UserInactiveException: 403,
    ForbiddenException: 403,
}


@app.exception_handler(DomainException)
def handle_domain_exception(request: Request, exc: DomainException):
    return JSONResponse(status_code=_STATUS_BY_EXCEPTION.get(type(exc), 400), content={"detail": str(exc)})


@app.get("/health")
def health():
    return {"status": "ok", "service": SERVICE_NAME}


app.include_router(user_router)


# --- Configuration technique ---------------------------------------------

DATABASE_URL = os.environ["DATABASE_URL"]
JWT_SECRET = os.environ.get("JWT_SECRET", "changeme-en-production")
JWT_EXPIRATION_MINUTES = int(os.environ.get("JWT_EXPIRATION_MINUTES", 60))

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

hasher = Pbkdf2HashingService()
tokens = JwtTokenService(JWT_SECRET, JWT_EXPIRATION_MINUTES)
notifier = ConsoleEmailNotificationService()


DEMO_PASSWORD = "demo1234"
DEMO_USERS = [
    ("Karim Ben Ali", "operateur@carbonghost.com", UserRole.OPERATOR, "B-1001"),
    ("Sonia Trabelsi", "chef.ligne@carbonghost.com", UserRole.LINE_MANAGER, "B-2001"),
    ("Amine Gharbi", "energie@carbonghost.com", UserRole.ENERGY_RSE_MANAGER, "B-3001"),
    ("Admin Plateforme", "admin.demo@carbonghost.com", UserRole.SUPER_ADMIN, "B-9001"),
]


@contextmanager
def use_cases():
    """Fournit les use cases avec une session SQLAlchemy dédiée à la requête."""
    session = SessionLocal()
    try:
        repo = PostgresUserRepository(session)
        yield SimpleNamespace(
            register=RegisterUserUseCase(repo, hasher, notifier),
            login=LoginUseCase(repo, hasher, tokens),
            get_current_user=GetCurrentUserUseCase(repo, tokens),
            list_users=ListUsersUseCase(repo),
            set_active=SetUserActiveUseCase(repo),
        )
    finally:
        session.close()


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(engine)  # crée la table "users" si elle n'existe pas

    accounts = []

    # Compte administrateur initial (si ADMIN_EMAIL et ADMIN_PASSWORD sont définis)
    email, password = os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD")
    if email and password:
        accounts.append(("admin", email, password, UserRole.SUPER_ADMIN, None))

    # Comptes de démonstration, un par rôle (SEED_DEMO_USERS=0 pour les désactiver)
    if os.environ.get("SEED_DEMO_USERS", "1") == "1":
        accounts += [(name, mail, DEMO_PASSWORD, role, badge) for name, mail, role, badge in DEMO_USERS]

    with SessionLocal() as session:
        repo = PostgresUserRepository(session)
        for username, mail, pwd, role, badge in accounts:
            if repo.get_user_by_email(mail.lower()) is None:
                repo.save_user(User(
                    id=str(uuid4()), username=username, email=mail.lower(),
                    hashed_password=hasher.hash_password(pwd), role=role, badge_id=badge,
                ))
