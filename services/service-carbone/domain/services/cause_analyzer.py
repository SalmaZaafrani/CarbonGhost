# domain/services/cause_analyzer.py — AUCUN import externe
"""
Explique un écart de consommation : à partir de la mesure capteur et de
l'énergie gaspillée, donne une cause probable, un niveau de confiance et
une action recommandée à l'opérateur.

Règles simples et explicables (MVP). Elles pourront être remplacées par
un modèle entraîné sans toucher au use case.
"""
from dataclasses import dataclass


@dataclass
class Diagnosis:
    probable_cause: str
    confidence: float
    recommendation: str
    status: str            # "normal" | "waste_detected"
    security_risk: str     # "low" | "medium" | "high"


@dataclass
class CauseAnalyzer:
    # Seuils configurables (valeurs par défaut adaptées au simulateur)
    idle_current_a: float = 3.0         # courant au-delà duquel une machine à l'arrêt consomme anormalement
    high_vibration: float = 4.0         # mm/s
    high_temperature: float = 70.0      # °C
    low_pressure: float = 4.0           # bar
    waste_ratio_threshold: float = 0.15  # gaspillage > 15 % de l'énergie attendue

    def analyze(
        self,
        courant: float,
        temperature: float,
        vibration: float,
        pression: float,
        production_count: int,
        actual_kwh: float,
        expected_kwh: float,
    ) -> Diagnosis:
        wasted = max(0.0, actual_kwh - expected_kwh)

        # 1. La machine consomme sans rien produire
        if production_count == 0 and courant > self.idle_current_a:
            return Diagnosis(
                "fonctionnement_a_vide", 0.9,
                "La machine consomme sans produire : la mettre en veille entre deux cycles.",
                "waste_detected", "low",
            )

        ratio = wasted / expected_kwh if expected_kwh > 0 else (1.0 if wasted > 0 else 0.0)
        if ratio <= self.waste_ratio_threshold:
            return Diagnosis("aucune", 0.8, "Consommation conforme à la production.", "normal", "low")

        # 2. Surconsommation avec un symptôme mécanique ou thermique
        if vibration > self.high_vibration:
            return Diagnosis(
                "usure_mecanique", 0.75,
                "Vibrations élevées : planifier une inspection des roulements et de l'alignement.",
                "waste_detected", "high",
            )
        if temperature > self.high_temperature:
            return Diagnosis(
                "surchauffe", 0.7,
                "Température élevée : vérifier le refroidissement et la lubrification.",
                "waste_detected", "medium",
            )
        if pression < self.low_pressure:
            return Diagnosis(
                "fuite_pneumatique", 0.6,
                "Pression basse : rechercher une fuite sur le circuit d'air comprimé.",
                "waste_detected", "medium",
            )

        # 3. Surconsommation sans symptôme visible
        return Diagnosis(
            "reglage_non_optimal", 0.5,
            "Surconsommation sans symptôme mécanique : vérifier les paramètres de réglage de la machine.",
            "waste_detected", "low",
        )
