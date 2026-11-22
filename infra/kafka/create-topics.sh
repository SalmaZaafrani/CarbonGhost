#!/bin/bash
# Crée les topics Kafka du système. Lancé automatiquement par le conteneur
# "kafka-init" de docker-compose une fois Kafka prêt.

set -e

BROKER="kafka:9092"

echo "Attente que Kafka soit prêt..."
until kafka-topics --bootstrap-server "$BROKER" --list > /dev/null 2>&1; do
  sleep 2
done

create_topic() {
  local name=$1
  local partitions=${2:-3}
  local replication=${3:-1}
  kafka-topics --bootstrap-server "$BROKER" \
    --create --if-not-exists \
    --topic "$name" \
    --partitions "$partitions" \
    --replication-factor "$replication"
  echo "Topic $name créé (partitions=$partitions, replication=$replication)"
}

# Mesures brutes publiées par service-mesures (consommées par carbone et ia)
create_topic "measures.raw" 3 1

# Événements carbone calculés par service-carbone (consommés par assistant)
create_topic "carbon.events" 3 1

# Alertes d'anomalies publiées par service-ia
create_topic "alerts" 3 1

# Explications générées par service-assistant
create_topic "assistant.explanations" 3 1

echo "Tous les topics sont prêts."
