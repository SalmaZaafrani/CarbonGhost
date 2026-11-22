import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from shared.security.auth import require

router = APIRouter(prefix="/carbone", tags=["carbone"])

READ_MACHINES = Depends(require("machines:read"))
READ_CARBON = Depends(require("carbon:read"))


class ObjectiveRequest(BaseModel):
    daily_co2_target_kg: float = Field(..., gt=0, description="CO2 évitable maximum accepté sur 24 h (kg)")


def _dto(e):
    return {
        "id": e.id,
        "machine_id": e.machine_id,
        "timestamp": e.timestamp,
        "actual_energy_kwh": e.actual_energy_kwh,
        "expected_energy_kwh": e.expected_energy_kwh,
        "wasted_energy_kwh": e.wasted_energy_kwh,
        "avoidable_co2_kg": e.avoidable_co2_kg,
        "status": e.status,
        "probable_cause": e.probable_cause,
        "confidence": e.confidence,
        "recommendation": e.recommendation,
    }


# ─────────────── Lecture des événements ───────────────

@router.get("/events", dependencies=[READ_MACHINES])
def list_recent_events(limit: int = Query(100, ge=1, le=1000), status: str | None = None):
    """Derniers événements carbone, toutes machines confondues."""
    from container import get_carbon_event_repository
    with get_carbon_event_repository() as repository:
        events = repository.find_recent(limit if not status else 1000)
        if status:
            events = [e for e in events if e.status == status][:limit]
        return [_dto(e) for e in events]


@router.get("/machines/{machine_id}/events", dependencies=[READ_MACHINES])
def list_events_by_machine(machine_id: str, limit: int = Query(100, ge=1, le=1000)):
    from container import get_carbon_event_repository
    with get_carbon_event_repository() as repository:
        return [_dto(e) for e in repository.find_by_machine(machine_id, limit)]


@router.get("/summary", dependencies=[READ_MACHINES])
def summary(hours: int | None = Query(None, ge=1, le=24 * 365)):
    """Énergie et CO2 évitable cumulés par machine (sur les `hours` dernières heures, ou depuis le début)."""
    from container import get_carbon_event_repository
    with get_carbon_event_repository() as repository:
        return repository.summary_by_machine(hours)


@router.get("/series", dependencies=[READ_CARBON])
def series(hours: int = Query(24, ge=1, le=24 * 31), bucket_minutes: int = Query(5, ge=1, le=1440)):
    """Évolution de l'énergie et du CO2 évitable, par tranche de temps."""
    from container import get_carbon_event_repository
    with get_carbon_event_repository() as repository:
        return repository.series(hours, bucket_minutes)


# ─────────────── Objectifs CO2 ───────────────

@router.get("/objectives", dependencies=[READ_CARBON])
def list_objectives():
    """Objectif de chaque machine et CO2 évitable réellement mesuré sur les dernières 24 h."""
    from container import get_carbon_event_repository, get_objective_repository
    with get_carbon_event_repository() as events, get_objective_repository() as objectives:
        actual = {s["machine_id"]: s["avoidable_co2_kg"] for s in events.summary_by_machine(hours=24)}
        targets = objectives.find_all()
        result = []
        for machine_id in sorted(set(actual) | set(targets)):
            target = targets.get(machine_id)
            co2 = actual.get(machine_id, 0.0)
            result.append({
                "machine_id": machine_id,
                "avoidable_co2_kg_24h": co2,
                "daily_co2_target_kg": target.daily_co2_target_kg if target else None,
                "progress_pct": round(co2 / target.daily_co2_target_kg * 100, 1) if target else None,
                "exceeded": bool(target and co2 > target.daily_co2_target_kg),
                "updated_by": target.updated_by if target else None,
                "updated_at": target.updated_at if target else None,
            })
        return result


@router.put("/objectives/{machine_id}")
def set_objective(machine_id: str, body: ObjectiveRequest,
                  user: dict = Depends(require("reports:export", "machines_config:manage"))):
    """Fixer l'objectif de CO2 d'une machine (responsable énergie ou administrateur)."""
    from container import get_objective_repository
    from domain.entities.objective import CarbonObjective

    objective = CarbonObjective(machine_id, body.daily_co2_target_kg,
                                updated_by=user.get("username") or user.get("email", ""))
    with get_objective_repository() as repository:
        repository.save(objective)
    return {"machine_id": machine_id, "daily_co2_target_kg": objective.daily_co2_target_kg,
            "updated_by": objective.updated_by, "updated_at": objective.updated_at}


# ─────────────── Export ───────────────

@router.get("/export.csv", dependencies=[Depends(require("reports:export"))])
def export_csv(hours: int = Query(24, ge=1, le=24 * 365)):
    """Export des événements carbone au format CSV (ouvrable dans Excel)."""
    from container import get_carbon_event_repository
    with get_carbon_event_repository() as repository:
        events = repository.find_since(hours)

    buffer = io.StringIO()
    buffer.write("﻿")  # BOM : Excel reconnaît l'UTF-8 et les accents
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(["horodatage", "machine", "energie_reelle_kwh", "energie_attendue_kwh",
                     "energie_gaspillee_kwh", "co2_evitable_kg", "statut", "cause_probable",
                     "confiance", "recommandation"])
    for e in events:
        writer.writerow([e.timestamp.isoformat(), e.machine_id, f"{e.actual_energy_kwh:.5f}",
                         f"{e.expected_energy_kwh:.5f}", f"{e.wasted_energy_kwh:.5f}", f"{e.avoidable_co2_kg:.5f}",
                         e.status, e.probable_cause, e.confidence, e.recommendation or ""])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="carbonghost_{hours}h.csv"'},
    )


@router.get("/events/{event_id}", dependencies=[READ_MACHINES])
def get_event(event_id: str):
    from container import get_carbon_event_repository
    from domain.exceptions.base_exceptions import NotFoundException

    with get_carbon_event_repository() as repository:
        event = repository.find_by_id(event_id)
        if event is None:
            raise NotFoundException(f"Événement carbone {event_id} introuvable")
        return _dto(event)
