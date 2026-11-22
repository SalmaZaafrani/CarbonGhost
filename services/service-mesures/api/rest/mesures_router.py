from fastapi import APIRouter, Depends, Query

from shared.security.auth import require

router = APIRouter(prefix="/mesures", tags=["mesures"], dependencies=[Depends(require("machines:read"))])


def _dto(m):
    return {
        "id": m.id,
        "machine_id": m.machine_id,
        "device_id": m.device_id,
        "timestamp": m.timestamp,
        "courant": m.courant,
        "temperature": m.temperature,
        "vibration": m.vibration,
        "pression": m.pression,
        "debit": m.debit,
        "production_count": m.production_count,
    }


@router.get("/latest")
def latest_per_machine():
    """Dernière mesure reçue pour chaque machine."""
    from container import get_measurement_repository
    with get_measurement_repository() as repository:
        return [_dto(m) for m in repository.find_latest_per_machine()]


@router.get("/machines/{machine_id}")
def list_measurements_by_machine(machine_id: str, limit: int = Query(100, ge=1, le=2000)):
    """Dernières mesures d'une machine (les plus récentes en premier)."""
    from container import get_measurement_repository
    with get_measurement_repository() as repository:
        return [_dto(m) for m in repository.find_by_machine(machine_id, limit)]


@router.get("/{measurement_id}")
def get_measurement(measurement_id: str):
    from container import get_measurement_repository
    from domain.exceptions.base_exceptions import NotFoundException

    with get_measurement_repository() as repository:
        m = repository.find_by_id(measurement_id)
        if m is None:
            raise NotFoundException(f"Mesure {measurement_id} introuvable")
        return _dto(m)
