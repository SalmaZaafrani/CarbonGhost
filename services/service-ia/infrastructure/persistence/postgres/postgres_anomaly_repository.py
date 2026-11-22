from sqlalchemy import func, select
from sqlalchemy.orm import Session

from domain.entities.anomaly import ACTIVE, Anomaly
from domain.ports.repositories.i_anomaly_repository import IAnomalyRepository
from infrastructure.persistence.postgres.models import AnomalyModel

FIELDS = ("id", "registered_at", "machine_id", "timestamp", "score", "severity", "status",
          "occurrences", "last_seen_at", "acknowledged_by", "acknowledged_at", "ack_comment")


class PostgresAnomalyRepository(IAnomalyRepository):
    def __init__(self, session: Session):
        self.session = session

    def save(self, anomaly: Anomaly) -> None:
        self.session.merge(AnomalyModel(
            **{f: getattr(anomaly, f) for f in FIELDS},
            features=",".join(anomaly.features),
        ))
        self.session.commit()

    def find_by_id(self, anomaly_id: str) -> Anomaly | None:
        model = self.session.get(AnomalyModel, anomaly_id)
        return self._to_entity(model) if model else None

    def find_by_machine(self, machine_id: str) -> list[Anomaly]:
        return self.find_recent(limit=500, machine_id=machine_id)

    def find_recent(self, limit: int = 100, status: str | None = None,
                    machine_id: str | None = None) -> list[Anomaly]:
        stmt = select(AnomalyModel).order_by(AnomalyModel.last_seen_at.desc()).limit(limit)
        if status:
            stmt = stmt.where(AnomalyModel.status == status)
        if machine_id:
            stmt = stmt.where(AnomalyModel.machine_id == machine_id)
        return [self._to_entity(m) for m in self.session.scalars(stmt).all()]

    def find_active(self, machine_id: str, main_feature: str) -> Anomaly | None:
        stmt = (
            select(AnomalyModel)
            .where(AnomalyModel.machine_id == machine_id, AnomalyModel.status == ACTIVE,
                   AnomalyModel.features.like(f"{main_feature}%"))
            .order_by(AnomalyModel.last_seen_at.desc())
            .limit(1)
        )
        model = self.session.scalars(stmt).first()
        return self._to_entity(model) if model else None

    def stats(self) -> dict:
        rows = self.session.execute(
            select(AnomalyModel.status, AnomalyModel.severity, func.count())
            .group_by(AnomalyModel.status, AnomalyModel.severity)
        ).all()
        result = {"active": {"critical": 0, "high": 0, "medium": 0}, "active_total": 0, "acknowledged_total": 0}
        for status, severity, count in rows:
            if status == ACTIVE:
                result["active"][severity] = result["active"].get(severity, 0) + count
                result["active_total"] += count
            else:
                result["acknowledged_total"] += count
        by_machine = self.session.execute(
            select(AnomalyModel.machine_id, func.count())
            .where(AnomalyModel.status == ACTIVE)
            .group_by(AnomalyModel.machine_id)
        ).all()
        result["active_by_machine"] = {m: c for m, c in by_machine}
        return result

    @staticmethod
    def _to_entity(m: AnomalyModel) -> Anomaly:
        return Anomaly(**{f: getattr(m, f) for f in FIELDS}, features=m.features.split(","))
