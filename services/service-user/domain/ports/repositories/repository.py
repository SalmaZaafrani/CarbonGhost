from abc import ABC, abstractmethod
from typing import Optional

from domain.entities.user import User


class IUserRepository(ABC):

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> Optional[User]: ...

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[User]: ...

    @abstractmethod
    def get_user_by_badge(self, badge_id: str) -> Optional[User]: ...

    @abstractmethod
    def list_users(self) -> list[User]: ...

    @abstractmethod
    def save_user(self, user: User) -> User:
        """Crée un nouvel utilisateur ou met à jour un utilisateur existant."""

    @abstractmethod
    def delete_user(self, user_id: str) -> None: ...
