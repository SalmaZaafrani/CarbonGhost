# Domaine pur : stdlib uniquement.
from collections import defaultdict, deque
from datetime import datetime
from math import sqrt
from statistics import median

from domain.entities.anomaly import Anomaly

FEATURES = ("courant", "temperature", "vibration", "pression")


class AnomalyDetector:
    """
    Détection par z-score glissant, par machine et par capteur.

    Chaque machine garde une fenêtre de ses dernières valeurs NORMALES.
    Une valeur trop éloignée de la moyenne (|z| > seuil) est une anomalie
    et n entre pas dans la fenêtre (évite de polluer la référence).
    Rien n est détecté avant `min_samples` valeurs (démarrage à froid).

    Deux règles limitent les fausses alarmes et couvrent l usure :
    - temporisation : un écart moyen doit se répéter sur `confirm_samples`
      mesures consécutives avant de lever une alarme (les écarts forts
      sont signalés tout de suite) ;
    - dérive : la moyenne glissante est comparée à une référence figée au
      démarrage ; un écart relatif > `drift_ratio` signale une usure lente
      que le z-score seul ne voit pas.
    """

    def __init__(self, window_size: int = 60, min_samples: int = 30, z_threshold: float = 4.0,
                 confirm_samples: int = 2, drift_ratio: float = 0.15):
        self.min_samples = min_samples
        self.z_threshold = z_threshold
        self.confirm_samples = confirm_samples
        self.drift_ratio = drift_ratio
        self._windows: dict[tuple[str, str], deque] = defaultdict(lambda: deque(maxlen=window_size))
        self._baselines: dict[tuple[str, str], float] = {}
        self._pending: dict[str, int] = defaultdict(int)

    def detect(self, machine_id: str, timestamp: datetime, values: dict[str, float]) -> Anomaly | None:
        faulty: dict[str, float] = {}

        for feature in FEATURES:
            value = values[feature]
            window = self._windows[(machine_id, feature)]

            z = self._zscore(window, value)
            if z is not None and abs(z) > self.z_threshold:
                faulty[feature] = abs(z)
            else:
                window.append(value)
                drift = self._drift(machine_id, feature, window)
                if drift is not None:
                    # Une dérive est notée comme un écart « fort » (sévérité haute)
                    faulty[feature] = self.z_threshold * 1.5 * max(1.0, drift / self.drift_ratio / 2)

        if not faulty:
            self._pending[machine_id] = 0
            return None

        score = max(faulty.values())
        if score < self.z_threshold * 1.5:
            self._pending[machine_id] += 1
            if self._pending[machine_id] < self.confirm_samples:
                return None
        self._pending[machine_id] = 0
        return Anomaly(
            machine_id=machine_id,
            timestamp=timestamp,
            features=sorted(faulty, key=faulty.get, reverse=True),
            score=round(score, 2),
            severity=self._severity(score),
        )

    def _drift(self, machine_id: str, feature: str, window: deque) -> float | None:
        if len(window) < window.maxlen:
            if len(window) == self.min_samples and (machine_id, feature) not in self._baselines:
                self._baselines[(machine_id, feature)] = median(window)  # robuste aux pics du démarrage
            return None
        base = self._baselines.get((machine_id, feature))
        if not base:
            return None
        ratio = abs(median(window) - base) / abs(base)
        return ratio if ratio > self.drift_ratio else None

    def _zscore(self, window: deque, value: float) -> float | None:
        n = len(window)
        if n < self.min_samples:
            return None
        mean = sum(window) / n
        std = sqrt(sum((x - mean) ** 2 for x in window) / n)
        std = max(std, 1e-6, abs(mean) * 0.01)  # plancher : évite la division par ~0
        return (value - mean) / std

    def _severity(self, score: float) -> str:
        if score >= self.z_threshold * 2:
            return "critical"
        if score >= self.z_threshold * 1.5:
            return "high"
        return "medium"
