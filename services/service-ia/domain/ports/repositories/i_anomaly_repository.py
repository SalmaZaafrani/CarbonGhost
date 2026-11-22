from abc import ABC, abstractmethod

from domain.entities.anomaly import Anomaly


class IAnomalyRepository(ABC):

    @abstractmethod
    def save(self, anomaly: Anomaly) -> None:
        """Crée ou met à jour l'anomalie."""

    @abstractmethod
    def find_by_id(self, anomaly_id: str) -> Anomaly | None: ...

    @abstractmethod
    def find_by_machine(self, machine_id: str) -> list[Anomaly]: ...

    @abstractmethod
    def find_recent(self, limit: int = 100, status: str | None = None,
                    machine_id: str | None = None) -> list[Anomaly]: ...

    @abstractmethod
    def find_active(self, machine_id: str, main_feature: str) -> Anomaly | None:
        """Alarme encore active pour ce défaut (même machine, même capteur principal)."""

    @abstractmethod
    def stats(self) -> dict: ...
