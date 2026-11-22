from uuid import uuid4

from application.dtos.user_dto import CreateUserCommand, UserResponseDTO
from application.ports import IEmailNotificationService, IHashingService, ITokenService
from domain.entities.authorization import Permission
from domain.entities.user import User
from domain.exceptions.exception import (
    AuthenticationFailedException,
    ForbiddenException,
    UserAlreadyExistsException,
    UserInactiveException,
    UserNotFoundException,
)
from domain.ports.repositories.repository import IUserRepository


def to_dto(user: User) -> UserResponseDTO:
    return UserResponseDTO(
        id=user.id, username=user.username, email=user.email, role=user.role,
        badge_id=user.badge_id, is_active=user.is_active, created_at=user.created_at,
    )


class RegisterUserUseCase:
    """Un utilisateur doit pouvoir créer un compte avec un email et un mot de passe."""

    def __init__(self, repository: IUserRepository, hasher: IHashingService, notifier: IEmailNotificationService):
        self.repository = repository
        self.hasher = hasher
        self.notifier = notifier

    def execute(self, command: CreateUserCommand) -> UserResponseDTO:
        email = command.email.lower()
        if self.repository.get_user_by_email(email):
            raise UserAlreadyExistsException("Un compte existe déjà avec cet email")
        if command.badge_id and self.repository.get_user_by_badge(command.badge_id):
            raise UserAlreadyExistsException("Ce badge est déjà attribué")

        user = User(
            id=str(uuid4()),
            username=command.username,
            email=email,
            hashed_password=self.hasher.hash_password(command.password),
            role=command.role,
            badge_id=command.badge_id,
        )
        self.repository.save_user(user)
        self.notifier.send_welcome_email(user.email, user.username)
        return to_dto(user)


class LoginUseCase:
    """Un utilisateur se connecte avec son email et son mot de passe, et reçoit un token."""

    def __init__(self, repository: IUserRepository, hasher: IHashingService, tokens: ITokenService):
        self.repository = repository
        self.hasher = hasher
        self.tokens = tokens

    def execute(self, email: str, password: str) -> dict:
        user = self.repository.get_user_by_email(email.lower())
        if user is None or not self.hasher.verify_password(password, user.hashed_password):
            raise AuthenticationFailedException("Email ou mot de passe incorrect")
        if not user.is_active:
            raise UserInactiveException()
        token = self.tokens.generate_token({
            "user_id": user.id,
            "email": user.email,
            "username": user.username,
            "role": user.role.value,
            "permissions": sorted(p.value for p in user.get_permissions()),
        })
        return {"access_token": token, "token_type": "bearer", "user": to_dto(user)}


class GetCurrentUserUseCase:
    """Retrouve l'utilisateur à partir de son token."""

    def __init__(self, repository: IUserRepository, tokens: ITokenService):
        self.repository = repository
        self.tokens = tokens

    def execute(self, token: str) -> User:
        try:
            payload = self.tokens.verify_token(token)
        except Exception:
            raise AuthenticationFailedException("Token invalide ou expiré")
        user = self.repository.get_user_by_id(payload["user_id"])
        if user is None:
            raise UserNotFoundException()
        if not user.is_active:
            raise UserInactiveException()
        return user


class ListUsersUseCase:
    def __init__(self, repository: IUserRepository):
        self.repository = repository

    def execute(self, requester: User) -> list[UserResponseDTO]:
        if not requester.has_permission(Permission.MANAGE_USERS):
            raise ForbiddenException()
        return [to_dto(u) for u in self.repository.list_users()]


class SetUserActiveUseCase:
    """Un administrateur active ou désactive un compte (ex : départ d'un ouvrier)."""

    def __init__(self, repository: IUserRepository):
        self.repository = repository

    def execute(self, requester: User, user_id: str, active: bool) -> UserResponseDTO:
        if not requester.has_permission(Permission.MANAGE_USERS):
            raise ForbiddenException()
        user = self.repository.get_user_by_id(user_id)
        if user is None:
            raise UserNotFoundException()
        user.activate() if active else user.desactivate()
        self.repository.save_user(user)
        return to_dto(user)
