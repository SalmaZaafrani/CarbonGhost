from domain.entities.anomaly import Anomaly
from domain.exceptions.base_exceptions import ConflictException, NotFoundException
from domain.ports.repositories.i_anomaly_repository import IAnomalyRepository


class AcknowledgeAlarmUseCase:
    """Un opérateur confirme avoir pris en compte une alarme (avec un commentaire facultatif)."""

    def __init__(self, repository: IAnomalyRepository):
        self.repository = repository

    def execute(self, alarm_id: str, by: str, comment: str | None = None) -> Anomaly:
        alarm = self.repository.find_by_id(alarm_id)
        if alarm is None:
            raise NotFoundException(f"Alarme {alarm_id} introuvable")
        try:
            alarm.acknowledge(by=by, comment=comment)
        except ValueError as e:
            raise ConflictException(str(e))
        self.repository.save(alarm)
        return alarm
