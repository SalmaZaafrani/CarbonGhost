from domain.entities.anomaly import Anomaly
from domain.ports.events.i_alert_publisher import IAlertPublisher
from domain.ports.repositories.i_anomaly_repository import IAnomalyRepository
from domain.services.anomaly_detector import AnomalyDetector
from shared.contracts.alert import Alert
from shared.contracts.sensor_measurement import SensorMeasurment


class DetectAnomalyUseCase:
    """
    Besoin métier : "à partir d une mesure capteur, dire si la machine
    se comporte anormalement, et alerter le cas échéant."
    """

    def __init__(self, repository: IAnomalyRepository, publisher: IAlertPublisher, detector: AnomalyDetector):
        self.repository = repository
        self.publisher = publisher
        self.detector = detector

    def execute(self, mesure: SensorMeasurment) -> Anomaly | None:
        anomaly = self.detector.detect(
            machine_id=mesure.machine_id,
            timestamp=mesure.timestamp,
            values={
                "courant": mesure.courant,
                "temperature": mesure.temperature,
                "vibration": mesure.vibration,
                "pression": mesure.pression,
            },
        )
        if anomaly is None:
            return None

        # Gestion du flot d'alarmes : un défaut déjà actif sur la même machine et
        # le même capteur est regroupé (occurrences) au lieu de créer une nouvelle alarme.
        existing = self.repository.find_active(anomaly.machine_id, anomaly.main_feature)
        if existing is not None:
            existing.repeat(anomaly)
            self.repository.save(existing)
            return existing

        self.repository.save(anomaly)
        self.publisher.publish(self._to_alert(anomaly))
        return anomaly

    @staticmethod
    def _to_alert(a: Anomaly) -> Alert:
        return Alert(
            id=a.id,
            machine_id=a.machine_id,
            timestamp=a.timestamp,
            type="anomaly",
            severity=a.severity,
            message=a.message,
        )
