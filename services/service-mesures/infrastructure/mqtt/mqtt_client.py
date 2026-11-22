import json

import paho.mqtt.client as mqtt
from pydantic import ValidationError

from shared.contracts.sensor_measurement import SensorMeasurment
from shared.observability.logger import get_logger

log = get_logger("mesures")

TOPIC = "capteurs/mesures"


def on_connect(client, userdata, flags, reason_code, properties=None):
    log("INFO", "Connecté au broker MQTT", extra={"reason_code": str(reason_code)})
    client.subscribe(TOPIC)
    log("INFO", f"Abonné au topic {TOPIC}")


def on_message(client, userdata, msg):
    from container import get_process_measurement_use_case  # import tardif (circulaire)

    try:
        payload = json.loads(msg.payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        log("WARNING", "Message MQTT ignoré : JSON invalide", extra={"topic": msg.topic})
        return

    try:
        mesure = SensorMeasurment(**payload)
    except ValidationError as e:
        log("WARNING", "Message MQTT ignoré : ne correspond pas à SensorMeasurment", extra={"erreur": str(e)})
        return

    # Une mesure en échec ne doit pas arrêter le listener MQTT
    try:
        with get_process_measurement_use_case() as use_case:
            use_case.execute(mesure)
        log("INFO", "Mesure traitée", machine_id=mesure.machine_id)
    except Exception as e:
        log("ERROR", "Échec du traitement de la mesure", machine_id=mesure.machine_id, extra={"erreur": str(e)})


def start_mqtt_listener(broker_address: str, broker_port: int = 1883) -> mqtt.Client:
    # API de callbacks v2 (obligatoire avec paho-mqtt >= 2.0)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    # connect_async + loop_start : le service démarre même si le broker n'est
    # pas encore prêt, et se reconnecte automatiquement.
    client.connect_async(broker_address, broker_port)
    client.loop_start()

    log("INFO", "Listener MQTT démarré", extra={"broker": f"{broker_address}:{broker_port}"})
    return client
