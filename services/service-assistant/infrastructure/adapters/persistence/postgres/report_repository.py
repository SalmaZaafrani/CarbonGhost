from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select

from infrastructure.adapters.persistence.postgres.models import ReportModel


class PostgresReportRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def save(self, content: str, period_hours: float, generated_by: str) -> dict:
        report = ReportModel(id=str(uuid4()), created_at=datetime.now(timezone.utc),
                             period_hours=period_hours, generated_by=generated_by, content=content)
        with self.session_factory() as session:
            session.add(report)
            session.commit()
            return self._dto(report)

    def list(self, limit: int = 30) -> list[dict]:
        with self.session_factory() as session:
            stmt = select(ReportModel).order_by(ReportModel.created_at.desc()).limit(limit)
            return [self._dto(r) for r in session.scalars(stmt)]

    def exists_since(self, hours: float, generated_by: str) -> bool:
        since = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self.session_factory() as session:
            stmt = select(ReportModel.id).where(ReportModel.created_at >= since,
                                                ReportModel.generated_by == generated_by).limit(1)
            return session.scalars(stmt).first() is not None

    @staticmethod
    def _dto(r: ReportModel) -> dict:
        return {"id": r.id, "created_at": r.created_at, "period_hours": r.period_hours,
                "generated_by": r.generated_by, "content": r.content}
