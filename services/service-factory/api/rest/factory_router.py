from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from shared.security.auth import require

READ = [Depends(require("machines:read"))]
MANAGE = [Depends(require("machines_config:manage"))]

router = APIRouter(prefix="/factory", tags=["factory"])


class MachineIn(BaseModel):
    id: str = Field(..., examples=["M4"], description="Identifiant utilisé par les capteurs (machine_id)")
    name: str = Field(..., examples=["Four de cuisson"])
    production_line: str = Field(..., examples=["Ligne B"])
    location: str = ""
    machine_type: str = ""
    nominal_power_kw: float = 0.0
    expected_kwh_per_unit: float = 0.1
    status: str = "active"


class MachineUpdate(BaseModel):
    name: str | None = None
    production_line: str | None = None
    location: str | None = None
    machine_type: str | None = None
    nominal_power_kw: float | None = None
    expected_kwh_per_unit: float | None = None
    status: str | None = None


@router.get("/machines", dependencies=READ)
def list_machines(production_line: str | None = None):
    from container import use_cases
    with use_cases() as uc:
        return uc.list.execute(production_line)


@router.post("/machines", status_code=201, dependencies=MANAGE)
def create_machine(body: MachineIn):
    from container import use_cases
    with use_cases() as uc:
        return uc.create.execute(body.model_dump())


@router.get("/machines/{machine_id}", dependencies=READ)
def get_machine(machine_id: str):
    from container import use_cases
    with use_cases() as uc:
        return uc.get.execute(machine_id)


@router.patch("/machines/{machine_id}", dependencies=MANAGE)
def update_machine(machine_id: str, body: MachineUpdate):
    from container import use_cases
    with use_cases() as uc:
        return uc.update.execute(machine_id, body.model_dump(exclude_none=True))


@router.delete("/machines/{machine_id}", status_code=204, dependencies=MANAGE)
def delete_machine(machine_id: str):
    from container import use_cases
    with use_cases() as uc:
        uc.delete.execute(machine_id)


@router.get("/lines", dependencies=READ)
def list_lines():
    """Lignes de production et leurs machines."""
    from container import use_cases
    with use_cases() as uc:
        lines: dict[str, list[str]] = {}
        for m in uc.list.execute():
            lines.setdefault(m.production_line, []).append(m.id)
        return [{"production_line": k, "machines": v} for k, v in sorted(lines.items())]
