# AUCUN import externe (FastAPI, SQLAlchemy, Kafka...)
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

ACTIVE = "active"
ACKNOWLEDGED = "acknowledged"


@dataclass
class Anomaly:
    """
    Anomalie capteur, gérée comme une alarme industrielle :
    elle reste « active » jusqu'à ce qu'une personne l'acquitte.
    Les répétitions d'un même défaut sont regroupées (occurrences).
    """

    machine_id: str
    timestamp: datetime
    features: list[str]   # capteurs hors norme, ex: ["vibration", "courant"]
    score: float          # z-score maximal observé
    severity: str         # "medium" | "high" | "critical"

    id: str = field(default_factory=lambda: str(uuid4()))
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    status: str = ACTIVE
    occurrences: int = 1
    last_seen_at: datetime | None = None
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    ack_comment: str | None = None

    def __post_init__(self):
        if not self.features:
            raise ValueError("une anomalie doit avoir au moins un capteur fautif")
        if self.last_seen_at is None:
            self.last_seen_at = self.timestamp

    @property
    def main_feature(self) -> str:
        return self.features[0]

    @property
    def message(self) -> str:
        return f"Anomalie sur {self.machine_id} : " + ", ".join(self.features) + f" (score {self.score:.1f})"

    def repeat(self, other: "Anomaly") -> None:
        """Le même défaut se reproduit : on met à jour l'alarme au lieu d'en créer une nouvelle."""
        self.occurrences += 1
        self.last_seen_at = other.timestamp
        if other.score > self.score:
            self.score, self.severity = other.score, other.severity
        self.features = sorted(set(self.features) | set(other.features), key=lambda f: f != other.main_feature)

    def acknowledge(self, by: str, comment: str | None = None, at: datetime | None = None) -> None:
        if self.status == ACKNOWLEDGED:
            raise ValueError("Cette alarme est déjà acquittée")
        self.status = ACKNOWLEDGED
        self.acknowledged_by = by
        self.acknowledged_at = at or datetime.now(timezone.utc)
        self.ack_comment = (comment or "").strip() or None
