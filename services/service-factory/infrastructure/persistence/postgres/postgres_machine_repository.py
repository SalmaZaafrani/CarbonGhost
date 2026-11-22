from sqlalchemy import select
from sqlalchemy.orm import Session

from domain.entities.machine import Machine
from domain.ports.repositories.i_machine_repository import IMachineRepository
from infrastructure.persistence.postgres.models import MachineModel

FIELDS = ("id", "name", "production_line", "location", "machine_type",
          "nominal_power_kw", "expected_kwh_per_unit", "status", "created_at")


class PostgresMachineRepository(IMachineRepository):
    def __init__(self, session: Session):
        self.session = session

    def save(self, machine: Machine) -> None:
        self.session.merge(MachineModel(**{f: getattr(machine, f) for f in FIELDS}))
        self.session.commit()

    def find_by_id(self, machine_id: str) -> Machine | None:
        model = self.session.get(MachineModel, machine_id)
        return self._to_entity(model) if model else None

    def find_all(self, production_line: str | None = None) -> list[Machine]:
        stmt = select(MachineModel).order_by(MachineModel.id)
        if production_line:
            stmt = stmt.where(MachineModel.production_line == production_line)
        return [self._to_entity(m) for m in self.session.scalars(stmt)]

    def delete(self, machine_id: str) -> None:
        model = self.session.get(MachineModel, machine_id)
        if model:
            self.session.delete(model)
            self.session.commit()

    @staticmethod
    def _to_entity(m: MachineModel) -> Machine:
        return Machine(**{f: getattr(m, f) for f in FIELDS})
