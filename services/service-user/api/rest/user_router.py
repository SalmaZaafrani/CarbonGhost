from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

from application.dtos.user_dto import CreateUserCommand, UserResponseDTO

router = APIRouter(prefix="/user", tags=["user"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/login/form")


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def current_user(token: str = Depends(oauth2_scheme)):
    from container import use_cases
    with use_cases() as uc:
        return uc.get_current_user.execute(token)


@router.post("/register", response_model=UserResponseDTO, status_code=201)
def register(command: CreateUserCommand):
    from container import use_cases
    with use_cases() as uc:
        return uc.register.execute(command)


@router.post("/login")
def login(body: LoginRequest):
    """Connexion par JSON : {"email": "...", "password": "..."}."""
    from container import use_cases
    with use_cases() as uc:
        return uc.login.execute(body.email, body.password)


@router.post("/login/form", include_in_schema=False)
def login_form(form: OAuth2PasswordRequestForm = Depends()):
    """Même connexion au format formulaire (bouton « Authorize » de /docs)."""
    from container import use_cases
    with use_cases() as uc:
        return uc.login.execute(form.username, form.password)


@router.get("/me", response_model=UserResponseDTO)
def me(user=Depends(current_user)):
    from application.use_cases.userUseCases import to_dto
    return to_dto(user)


@router.get("/me/permissions")
def my_permissions(user=Depends(current_user)):
    return sorted(p.value for p in user.get_permissions())


@router.get("/", response_model=list[UserResponseDTO])
def list_users(user=Depends(current_user)):
    """Réservé aux rôles ayant la permission users:manage."""
    from container import use_cases
    with use_cases() as uc:
        return uc.list_users.execute(user)


@router.patch("/{user_id}/active", response_model=UserResponseDTO)
def set_active(user_id: str, active: bool, user=Depends(current_user)):
    from container import use_cases
    with use_cases() as uc:
        return uc.set_active.execute(user, user_id, active)
