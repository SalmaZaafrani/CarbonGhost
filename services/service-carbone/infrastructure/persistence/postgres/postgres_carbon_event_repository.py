from datetime import datetime, timedelta, timezone

from sqlalchemy import select, delete, func, case
from sqlalchemy.orm import Session

from domain.entities.carbon_event import CarbonEvent
from domain.ports.repositories.i_carbon_event_repository import ICarbonEventRepository
from infrastructure.persistence.postgres.models import CarbonEventModel


class PostgresCarbonEventRepository(ICarbonEventRepository):
    def __init__(self, session: Session):
        self.session = session

    def save(self, event: CarbonEvent) -> None:
        model = CarbonEventModel(
            id=event.id,
            registered_at=event.registered_at,
            machine_id=event.machine_id,
            timestamp=event.timestamp,
            actual_energy_kwh=event.actual_energy_kwh,
            expected_energy_kwh=event.expected_energy_kwh,
            carbon_factor=event.carbon_factor,
            probable_cause=event.probable_cause,
            confidence=event.confidence,
            security_risk=event.security_risk,
            status=event.status,
            recommendation=event.recommendation,
        )
        self.session.add(model)
        self.session.commit()

    def find_by_id(self, event_id: str) -> CarbonEvent | None:
        model = self.session.get(CarbonEventModel, event_id)
        return self._to_entity(model) if model else None

    def find_by_machine(self, machine_id: str, limit: int | None = None) -> list[CarbonEvent]:
        stmt = (
            select(CarbonEventModel)
            .where(CarbonEventModel.machine_id == machine_id)
            .order_by(CarbonEventModel.timestamp.desc())
            .limit(limit)
        )
        models = self.session.scalars(stmt).all()
        return [self._to_entity(m) for m in models]

    def find_recent(self, limit: int = 100) -> list[CarbonEvent]:
        stmt = select(CarbonEventModel).order_by(CarbonEventModel.timestamp.desc()).limit(limit)
        return [self._to_entity(m) for m in self.session.scalars(stmt).all()]

    def find_since(self, hours: int) -> list[CarbonEvent]:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        stmt = select(CarbonEventModel).where(CarbonEventModel.timestamp >= since).order_by(CarbonEventModel.timestamp)
        return [self._to_entity(m) for m in self.session.scalars(stmt).all()]

    def series(self, hours: int, bucket_minutes: int) -> list[dict]:
        """Énergie et CO2 évitable agrégés par tranche de temps (toutes machines)."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        seconds = bucket_minutes * 60
        bucket = func.to_timestamp(func.floor(func.extract("epoch", CarbonEventModel.timestamp) / seconds) * seconds)
        wasted = func.greatest(CarbonEventModel.actual_energy_kwh - CarbonEventModel.expected_energy_kwh, 0)
        stmt = (
            select(
                bucket.label("bucket"),
                func.sum(CarbonEventModel.actual_energy_kwh).label("actual_kwh"),
                func.sum(CarbonEventModel.expected_energy_kwh).label("expected_kwh"),
                func.sum(wasted * CarbonEventModel.carbon_factor).label("avoidable_co2_kg"),
            )
            .where(CarbonEventModel.timestamp >= since)
            .group_by("bucket")
            .order_by("bucket")
        )
        return [
            {"bucket": r.bucket, "actual_kwh": round(r.actual_kwh, 4), "expected_kwh": round(r.expected_kwh, 4),
             "avoidable_co2_kg": round(r.avoidable_co2_kg, 4)}
            for r in self.session.execute(stmt)
        ]

    def summary_by_machine(self, hours: int | None = None) -> list[dict]:
        wasted = func.greatest(CarbonEventModel.actual_energy_kwh - CarbonEventModel.expected_energy_kwh, 0)
        stmt = (
            select(
                CarbonEventModel.machine_id,
                func.count().label("events"),
                func.sum(CarbonEventModel.actual_energy_kwh).label("actual_kwh"),
                func.sum(CarbonEventModel.expected_energy_kwh).label("expected_kwh"),
                func.sum(wasted).label("wasted_kwh"),
                func.sum(wasted * CarbonEventModel.carbon_factor).label("avoidable_co2_kg"),
                func.sum(case((CarbonEventModel.status == "waste_detected", 1), else_=0)).label("waste_events"),
            )
            .group_by(CarbonEventModel.machine_id)
            .order_by(CarbonEventModel.machine_id)
        )
        if hours:
            stmt = stmt.where(CarbonEventModel.timestamp >= datetime.now(timezone.utc) - timedelta(hours=hours))
        return [
            {
                "machine_id": r.machine_id,
                "events": r.events,
                "waste_events": int(r.waste_events or 0),
                "actual_kwh": round(r.actual_kwh or 0, 4),
                "expected_kwh": round(r.expected_kwh or 0, 4),
                "wasted_kwh": round(r.wasted_kwh or 0, 4),
                "avoidable_co2_kg": round(r.avoidable_co2_kg or 0, 4),
            }
            for r in self.session.execute(stmt)
        ]

    def delete_by_machine(self, machine_id: str) -> int:
        stmt = delete(CarbonEventModel).where(CarbonEventModel.machine_id == machine_id)
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount

    def _to_entity(self, model: CarbonEventModel) -> CarbonEvent:
        return CarbonEvent(
            id=model.id,
            registered_at=model.registered_at,
            machine_id=model.machine_id,
            timestamp=model.timestamp,
            actual_energy_kwh=model.actual_energy_kwh,
            expected_energy_kwh=model.expected_energy_kwh,
            carbon_factor=model.carbon_factor,
            probable_cause=model.probable_cause,
            confidence=model.confidence,
            security_risk=model.security_risk,
            status=model.status,
            recommendation=model.recommendation,
        )
