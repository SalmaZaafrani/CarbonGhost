# AUCUN import externe
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class CarbonObjective:
    """Plafond de CO2 évitable que l'usine se fixe pour une machine, sur 24 heures."""

    machine_id: str
    daily_co2_target_kg: float
    updated_by: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self):
        if self.daily_co2_target_kg <= 0:
            raise ValueError("L'objectif doit être strictement positif")
