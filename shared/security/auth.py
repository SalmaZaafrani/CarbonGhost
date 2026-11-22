"""
Vérification des tokens JWT émis par service-user, commune à tous les services.

Le token contient le rôle et la liste des permissions de l'utilisateur :
chaque service peut donc contrôler l'accès sans appeler service-user.

Usage dans un router FastAPI :

    from shared.security.auth import require

    @router.get("/machines", dependencies=[Depends(require("machines:read"))])
    def list_machines(): ...

    @router.post("/alarms/{id}/acknowledge")
    def ack(id: str, user: dict = Depends(require("alarms:ack"))):
        user["email"] ...
"""
import os

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

_bearer = HTTPBearer(auto_error=False)


def _secret() -> str:
    return os.environ.get("JWT_SECRET", "changeme-en-production")


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Décode le token « Authorization: Bearer ... » et renvoie son contenu."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Connexion requise",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        return jwt.decode(credentials.credentials, _secret(), algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expirée, reconnectez-vous")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide")


def require(*permissions: str):
    """Dépendance FastAPI : l'utilisateur doit avoir AU MOINS UNE des permissions données."""
    def checker(user: dict = Depends(current_user)) -> dict:
        granted = set(user.get("permissions", []))
        if permissions and not granted.intersection(permissions):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Permission insuffisante")
        return user
    return checker
