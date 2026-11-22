from datetime import datetime
from typing import List

from sqlalchemy import select

from domain.entities.carbon_event import CarbonEvent
from domain.ports.repositories.i_carbon_event_repository import ICarbonEventRepository
from infrastructure.adapters.persistence.postgres.models import CarbonGhostEventModel


class PostgresCarbonEventRepository(ICarbonEventRepository):
    """Chaque méthode ouvre sa propre session : utilisable depuis le thread Kafka et l'API."""

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def save(self, event: CarbonEvent) -> None:
        with self.session_factory() as session:
            session.merge(CarbonGhostEventModel(**event.__dict__))
            session.commit()

    def get_recent_events(self, limit: int = 20) -> List[CarbonEvent]:
        stmt = select(CarbonGhostEventModel).order_by(CarbonGhostEventModel.timestamp.desc()).limit(limit)
        return self._fetch(stmt)

    def get_events_between(self, start: datetime, end: datetime) -> List[CarbonEvent]:
        stmt = (
            select(CarbonGhostEventModel)
            .where(CarbonGhostEventModel.timestamp.between(start, end))
            .order_by(CarbonGhostEventModel.timestamp.desc())
        )
        return self._fetch(stmt)

    def get_events_by_machine(self, machine_id: str, limit: int = 20) -> List[CarbonEvent]:
        stmt = (
            select(CarbonGhostEventModel)
            .where(CarbonGhostEventModel.machine_id == machine_id)
            .order_by(CarbonGhostEventModel.timestamp.desc())
            .limit(limit)
        )
        return self._fetch(stmt)

    def get_context_for_llm(self, machine_id: str) -> dict:
        events = self.get_events_by_machine(machine_id, limit=60)
        if not events:
            return {}
        latest = events[0]
        waste = [e for e in events if e.status == "waste_detected"]
        causes, recommendations = {}, {}
        for e in waste:
            causes[e.probable_cause] = causes.get(e.probable_cause, 0) + 1
            recommendations.setdefault(e.probable_cause, e.recommendation)
        return {
            "machine_id": latest.machine_id,
            "timestamp": latest.timestamp,
            "expected_energy": round(latest.expected_energy_kwh or 0, 4),
            "actual_energy": round(latest.actual_energy_kwh or 0, 4),
            "deviation_pct": latest.surconsommation_pct,
            "probable_cause": latest.probable_cause,
            "recommendation": latest.recommendation,
            "events_analyzed": len(events),
            "waste_events": len(waste),
            "avoidable_co2_kg": round(sum(e.avoidable_co2_kg or 0 for e in events), 4),
            "main_causes": sorted(causes.items(), key=lambda kv: kv[1], reverse=True),
            "recommendations": recommendations,
            "wasted_kwh": round(sum(max((e.actual_energy_kwh or 0) - (e.expected_energy_kwh or 0), 0) for e in events), 4),
        }

    def _fetch(self, stmt) -> List[CarbonEvent]:
        with self.session_factory() as session:
            return [self._to_entity(m) for m in session.scalars(stmt).all()]

    @staticmethod
    def _to_entity(m: CarbonGhostEventModel) -> CarbonEvent:
        return CarbonEvent(
            id=m.id,
            machine_id=m.machine_id,
            timestamp=m.timestamp,
            actual_energy_kwh=m.actual_energy_kwh,
            expected_energy_kwh=m.expected_energy_kwh,
            surconsommation_pct=m.surconsommation_pct,
            avoidable_co2_kg=m.avoidable_co2_kg,
            probable_cause=m.probable_cause,
            confidence=m.confidence,
            recommendation=m.recommendation,
            status=m.status,
        )
