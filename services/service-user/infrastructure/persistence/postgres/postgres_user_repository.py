from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.entities.authorization import UserRole
from domain.entities.user import User
from domain.ports.repositories.repository import IUserRepository
from infrastructure.persistence.postgres.models import UserModel


class PostgresUserRepository(IUserRepository):
    def __init__(self, session: Session):
        self.session = session

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        model = self.session.get(UserModel, str(user_id))
        return self._to_entity(model) if model else None

    def get_user_by_email(self, email: str) -> Optional[User]:
        model = self.session.scalars(select(UserModel).where(UserModel.email == email)).first()
        return self._to_entity(model) if model else None

    def get_user_by_badge(self, badge_id: str) -> Optional[User]:
        model = self.session.scalars(select(UserModel).where(UserModel.badge_id == badge_id)).first()
        return self._to_entity(model) if model else None

    def list_users(self) -> list[User]:
        return [self._to_entity(m) for m in self.session.scalars(select(UserModel).order_by(UserModel.created_at))]

    def save_user(self, user: User) -> User:
        self.session.merge(UserModel(
            id=user.id, username=user.username, email=user.email, hashed_password=user.hashed_password,
            role=user.role.value, badge_id=user.badge_id, is_active=user.is_active, created_at=user.created_at,
        ))
        self.session.commit()
        return user

    def delete_user(self, user_id: str) -> None:
        model = self.session.get(UserModel, str(user_id))
        if model:
            self.session.delete(model)
            self.session.commit()

    @staticmethod
    def _to_entity(m: UserModel) -> User:
        return User(
            id=m.id, username=m.username, email=m.email, hashed_password=m.hashed_password,
            role=UserRole(m.role), badge_id=m.badge_id, is_active=m.is_active, created_at=m.created_at,
        )
