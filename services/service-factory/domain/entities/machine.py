# domain/entities/machine.py — AUCUN import externe
from dataclasses import dataclass, field
from datetime import datetime, timezone

STATUSES = ("active", "maintenance", "stopped")


@dataclass
class Machine:
    """Une machine de l'usine, identifiée par le même machine_id que dans les mesures capteurs."""

    id: str                          # ex : "M1" (identifiant utilisé par les capteurs)
    name: str                        # ex : "Presse hydraulique"
    production_line: str             # ex : "Ligne A"
    location: str = ""               # ex : "Atelier 1"
    machine_type: str = ""           # ex : "presse", "compresseur"
    nominal_power_kw: float = 0.0
    expected_kwh_per_unit: float = 0.1  # référence de consommation par pièce produite
    status: str = "active"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if not self.id or not self.id.strip():
            raise ValueError("L'identifiant de la machine est obligatoire")
        if not self.name.strip():
            raise ValueError("Le nom de la machine est obligatoire")
        if self.nominal_power_kw < 0 or self.expected_kwh_per_unit < 0:
            raise ValueError("Les valeurs de puissance ne peuvent pas être négatives")
        if self.status not in STATUSES:
            raise ValueError(f"Statut invalide : {self.status} (attendu : {', '.join(STATUSES)})")
