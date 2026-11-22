from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.entities.objective import CarbonObjective
from infrastructure.persistence.postgres.models import CarbonObjectiveModel


class PostgresObjectiveRepository:
    def __init__(self, session: Session):
        self.session = session

    def save(self, objective: CarbonObjective) -> None:
        self.session.merge(CarbonObjectiveModel(**objective.__dict__))
        self.session.commit()

    def find_all(self) -> dict[str, CarbonObjective]:
        return {
            m.machine_id: CarbonObjective(m.machine_id, m.daily_co2_target_kg, m.updated_by, m.updated_at)
            for m in self.session.scalars(select(CarbonObjectiveModel))
        }
