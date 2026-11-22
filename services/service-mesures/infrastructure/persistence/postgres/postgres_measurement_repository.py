from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from domain.entities.measurement import Measurement
from domain.ports.repositories.i_measurement_repository import IMeasurementRepository
from infrastructure.persistence.postgres.models import MeasurementModel


class PostgresMeasurementRepository(IMeasurementRepository):
    def __init__(self, session: Session):
        self.session = session

    def save(self, measurement: Measurement) -> None:
        model = MeasurementModel(
            id=measurement.id,
            registered_at=measurement.registered_at,
            machine_id=measurement.machine_id,
            device_id=measurement.device_id,
            timestamp=measurement.timestamp,
            courant=measurement.courant,
            temperature=measurement.temperature,
            vibration=measurement.vibration,
            pression=measurement.pression,
            debit=measurement.debit,
            production_count=measurement.production_count,
        )
        self.session.add(model)
        self.session.commit()

    def find_by_id(self, measurement_id: str) -> Measurement | None:
        model = self.session.get(MeasurementModel, measurement_id)
        return self._to_entity(model) if model else None

    def find_by_machine(self, machine_id: str, limit: int | None = None) -> list[Measurement]:
        stmt = (
            select(MeasurementModel)
            .where(MeasurementModel.machine_id == machine_id)
            .order_by(MeasurementModel.timestamp.desc())
            .limit(limit)
        )
        models = self.session.scalars(stmt).all()
        return [self._to_entity(m) for m in models]

    def delete_by_machine(self, machine_id: str) -> int:
        stmt = delete(MeasurementModel).where(MeasurementModel.machine_id == machine_id)
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount

    def _to_entity(self, model: MeasurementModel) -> Measurement:
        return Measurement(
            id=model.id,
            registered_at=model.registered_at,
            machine_id=model.machine_id,
            device_id=model.device_id,
            timestamp=model.timestamp,
            courant=model.courant,
            temperature=model.temperature,
            vibration=model.vibration,
            pression=model.pression,
            debit=model.debit,
            production_count=model.production_count,
        )

    def find_latest_per_machine(self) -> list:
        """Dernière mesure reçue pour chaque machine (vue synoptique)."""
        from sqlalchemy import func
        latest = (
            select(MeasurementModel.machine_id, func.max(MeasurementModel.timestamp).label("ts"))
            .group_by(MeasurementModel.machine_id)
            .subquery()
        )
        stmt = (
            select(MeasurementModel)
            .join(latest, (MeasurementModel.machine_id == latest.c.machine_id) & (MeasurementModel.timestamp == latest.c.ts))
            .order_by(MeasurementModel.machine_id)
        )
        seen, result = set(), []
        for m in self.session.scalars(stmt).all():
            if m.machine_id not in seen:
                seen.add(m.machine_id)
                result.append(self._to_entity(m))
        return result
