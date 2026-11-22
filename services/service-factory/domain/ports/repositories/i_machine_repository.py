from abc import ABC, abstractmethod

from domain.entities.machine import Machine


class IMachineRepository(ABC):

    @abstractmethod
    def save(self, machine: Machine) -> None: ...

    @abstractmethod
    def find_by_id(self, machine_id: str) -> Machine | None: ...

    @abstractmethod
    def find_all(self, production_line: str | None = None) -> list[Machine]: ...

    @abstractmethod
    def delete(self, machine_id: str) -> None: ...
