from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from shared.security.auth import require

router = APIRouter(prefix="/ia", tags=["ia"], dependencies=[Depends(require("machines:read"))])


class AcknowledgeRequest(BaseModel):
    comment: str | None = None


def _dto(a):
    return {
        "id": a.id,
        "machine_id": a.machine_id,
        "timestamp": a.timestamp,
        "last_seen_at": a.last_seen_at,
        "features": a.features,
        "score": a.score,
        "severity": a.severity,
        "message": a.message,
        "status": a.status,
        "occurrences": a.occurrences,
        "acknowledged_by": a.acknowledged_by,
        "acknowledged_at": a.acknowledged_at,
        "ack_comment": a.ack_comment,
    }


@router.get("/alarms")
def list_alarms(status: str | None = Query(None, pattern="^(active|acknowledged)$"),
                machine_id: str | None = None, limit: int = Query(100, ge=1, le=1000)):
    """Alarmes (anomalies capteurs), des plus récentes aux plus anciennes."""
    from container import get_anomaly_repository
    with get_anomaly_repository() as repository:
        return [_dto(a) for a in repository.find_recent(limit, status=status, machine_id=machine_id)]


@router.get("/alarms/stats")
def alarm_stats():
    """Nombre d'alarmes actives par sévérité et par machine."""
    from container import get_anomaly_repository
    with get_anomaly_repository() as repository:
        return repository.stats()


@router.post("/alarms/{alarm_id}/acknowledge")
def acknowledge_alarm(alarm_id: str, body: AcknowledgeRequest, user: dict = Depends(require("alarms:ack"))):
    from container import get_acknowledge_use_case
    with get_acknowledge_use_case() as use_case:
        return _dto(use_case.execute(alarm_id, by=user.get("username") or user.get("email"), comment=body.comment))


# Routes historiques, conservées pour compatibilité
@router.get("/anomalies")
def list_recent_anomalies(limit: int = Query(50, ge=1, le=500)):
    from container import get_anomaly_repository
    with get_anomaly_repository() as repository:
        return [_dto(a) for a in repository.find_recent(limit)]


@router.get("/machines/{machine_id}/anomalies")
def list_anomalies_by_machine(machine_id: str):
    from container import get_anomaly_repository
    with get_anomaly_repository() as repository:
        return [_dto(a) for a in repository.find_by_machine(machine_id)]


@router.get("/anomalies/{anomaly_id}")
def get_anomaly(anomaly_id: str):
    from container import get_anomaly_repository
    from domain.exceptions.base_exceptions import NotFoundException

    with get_anomaly_repository() as repository:
        anomaly = repository.find_by_id(anomaly_id)
        if anomaly is None:
            raise NotFoundException(f"Anomalie {anomaly_id} introuvable")
        return _dto(anomaly)
