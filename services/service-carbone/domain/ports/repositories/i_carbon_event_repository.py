from abc import ABC, abstractmethod

from domain.entities.carbon_event import CarbonEvent


class ICarbonEventRepository(ABC):

    @abstractmethod
    def save(self, event: CarbonEvent) -> None:
        ...

    @abstractmethod
    def find_by_id(self, event_id: str) -> CarbonEvent | None:
        ...

    @abstractmethod
    def find_by_machine(self, machine_id: str) -> list[CarbonEvent]:
        ...

    @abstractmethod
    def find_recent(self, limit: int = 100) -> list[CarbonEvent]: ...

    @abstractmethod
    def summary_by_machine(self, hours: int | None = None) -> list[dict]: ...

    @abstractmethod
    def series(self, hours: int, bucket_minutes: int) -> list[dict]: ...

    @abstractmethod
    def find_since(self, hours: int) -> list[CarbonEvent]: ...

    @abstractmethod
    def delete_by_machine(self, machine_id: str) -> None:
        """Opération destructive et irréversible"""
        ...
