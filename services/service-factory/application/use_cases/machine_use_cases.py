from domain.entities.machine import Machine
from domain.exceptions.exception import ConflictException, NotFoundException, ValidationException
from domain.ports.repositories.i_machine_repository import IMachineRepository


class CreateMachineUseCase:
    """Enregistrer une nouvelle machine de l'usine."""

    def __init__(self, repository: IMachineRepository):
        self.repository = repository

    def execute(self, data: dict) -> Machine:
        if self.repository.find_by_id(data["id"]):
            raise ConflictException(f"La machine {data['id']} existe déjà")
        try:
            machine = Machine(**data)
        except ValueError as e:
            raise ValidationException(str(e))
        self.repository.save(machine)
        return machine


class UpdateMachineUseCase:
    """Modifier une machine (nom, ligne, statut...)."""

    def __init__(self, repository: IMachineRepository):
        self.repository = repository

    def execute(self, machine_id: str, changes: dict) -> Machine:
        machine = self.repository.find_by_id(machine_id)
        if machine is None:
            raise NotFoundException(f"Machine {machine_id} introuvable")
        try:
            updated = Machine(**{**machine.__dict__, **changes, "id": machine.id})
        except ValueError as e:
            raise ValidationException(str(e))
        self.repository.save(updated)
        return updated


class GetMachineUseCase:
    def __init__(self, repository: IMachineRepository):
        self.repository = repository

    def execute(self, machine_id: str) -> Machine:
        machine = self.repository.find_by_id(machine_id)
        if machine is None:
            raise NotFoundException(f"Machine {machine_id} introuvable")
        return machine


class ListMachinesUseCase:
    def __init__(self, repository: IMachineRepository):
        self.repository = repository

    def execute(self, production_line: str | None = None) -> list[Machine]:
        return self.repository.find_all(production_line)


class DeleteMachineUseCase:
    def __init__(self, repository: IMachineRepository):
        self.repository = repository

    def execute(self, machine_id: str) -> None:
        if self.repository.find_by_id(machine_id) is None:
            raise NotFoundException(f"Machine {machine_id} introuvable")
        self.repository.delete(machine_id)
