import asyncio
import logging
import os
import threading
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings
from domain.entities.carbon_event import CarbonEvent
from infrastructure.adapters.llm.groq_client import GroqAssistantClient
from infrastructure.adapters.kafka.kafka_carbon_event_consumer import KafkaCarbonEventConsumer
from infrastructure.adapters.persistence.postgres.models import Base
from infrastructure.adapters.persistence.postgres.carbon_event_repository import (
    PostgresCarbonEventRepository,
)
from infrastructure.adapters.persistence.postgres.report_repository import PostgresReportRepository

log = logging.getLogger("service-assistant")

# Rapport automatique : toutes les REPORT_INTERVAL_HOURS heures (0 = désactivé)
REPORT_INTERVAL_HOURS = float(os.environ.get("REPORT_INTERVAL_HOURS", 24))
AUTO_REPORT_AUTHOR = "automatique"
from application.use_cases.ask_assistant_use_case import AskAssistantUseCase
from application.use_cases.generate_report_use_case import GenerateReportUseCase


class Container:
    def __init__(self):
        # LLM (optionnel)
        self.llm = GroqAssistantClient()

        # Base de données
        self.engine = create_engine(settings.database_url, pool_pre_ping=True)
        self.session_factory = sessionmaker(bind=self.engine)
        self.repository = PostgresCarbonEventRepository(self.session_factory)
        self.reports = PostgresReportRepository(self.session_factory)

        # Use cases
        self.ask_use_case = AskAssistantUseCase(self.repository, self.llm)
        self.report_use_case = GenerateReportUseCase(self.repository, self.llm)

        self.carbon_event_consumer = None

    def _handle_incoming_event(self, event):
        """Chaque événement carbone reçu est enregistré localement pour répondre aux questions."""
        pct = None
        if event.expected_energy_kwh > 0:
            pct = round((event.actual_energy_kwh - event.expected_energy_kwh) / event.expected_energy_kwh * 100, 1)
        self.repository.save(CarbonEvent(
            id=event.id,
            machine_id=event.machine_id,
            timestamp=event.timestamp,
            actual_energy_kwh=event.actual_energy_kwh,
            expected_energy_kwh=event.expected_energy_kwh,
            surconsommation_pct=pct,
            avoidable_co2_kg=event.avoidable_co2_kg,
            probable_cause=event.probable_cause,
            confidence=event.confidence,
            recommendation=event.recommendation,
            status=event.status,
        ))

    def start(self):
        Base.metadata.create_all(self.engine)  # crée la table "carbon_ghost_events"
        self.carbon_event_consumer = KafkaCarbonEventConsumer(
            broker_address=settings.kafka_broker,
            group_id="service-assistant",
        )
        threading.Thread(
            target=self.carbon_event_consumer.consume,
            args=(self._handle_incoming_event,),
            daemon=True,
        ).start()
        if REPORT_INTERVAL_HOURS > 0:
            threading.Thread(target=self._auto_reports, daemon=True).start()

    def _auto_reports(self):
        """Génère un rapport automatique à intervalle régulier (premier rapport 2 min après le démarrage)."""
        time.sleep(120)
        while True:
            try:
                if not self.reports.exists_since(REPORT_INTERVAL_HOURS * 0.95, AUTO_REPORT_AUTHOR):
                    content = asyncio.run(self.report_use_case.execute(hours=max(1, round(REPORT_INTERVAL_HOURS))))
                    self.reports.save(content, REPORT_INTERVAL_HOURS, AUTO_REPORT_AUTHOR)
                    log.warning("Rapport automatique généré")
            except Exception as e:
                log.error("Échec du rapport automatique : %s", e)
            time.sleep(min(REPORT_INTERVAL_HOURS * 3600, 3600))


container = Container()
