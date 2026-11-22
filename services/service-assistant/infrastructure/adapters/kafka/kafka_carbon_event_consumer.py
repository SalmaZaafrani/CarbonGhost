import json
from typing import Callable

from confluent_kafka import Consumer
from pydantic import ValidationError

from domain.ports.events.i_carbon_event_consumer import ICarbonEventConsumer
from shared.contracts.carbon_ghost_event import CarbonGhostEvent
from shared.observability.logger import get_logger

log = get_logger("assistant")

# Événements publiés par service-carbone
TOPIC = "carbon.events"


class KafkaCarbonEventConsumer(ICarbonEventConsumer):
    def __init__(self, broker_address: str, group_id: str = "service-assistant"):
        self.consumer = Consumer({
            "bootstrap.servers": broker_address,
            "group.id": group_id,
            "auto.offset.reset": "earliest",
        })
        self.consumer.subscribe([TOPIC])

    def consume(self, handler: Callable[[CarbonGhostEvent], None]) -> None:
        log("INFO", "Consumer Kafka démarré", extra={"topic": TOPIC})
        while True:
            msg = self.consumer.poll(1.0)
            if msg is None:
                continue
            if msg.error():
                log("WARNING", "Erreur Kafka", extra={"erreur": str(msg.error())})
                continue
            try:
                event = CarbonGhostEvent(**json.loads(msg.value().decode("utf-8")))
                handler(event)
            except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as e:
                log("WARNING", "Message ignoré : invalide", extra={"erreur": str(e)})
            except Exception as e:  # un message en échec ne doit pas tuer le thread
                log("ERROR", "Échec du traitement de l'événement", extra={"erreur": str(e)})
