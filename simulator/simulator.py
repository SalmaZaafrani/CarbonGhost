"""
Simulateur de capteurs CarbonGhost.

Remplace l'ESP32 et l'edge-gateway pendant le développement : publie des
mesures sur le broker MQTT (topic capteurs/mesures), au format attendu par
service-mesures (shared/contracts/sensor_measurement.py).

Chaque machine suit un scénario, pour que toute la chaîne ait quelque chose
à détecter :
  M1  normal         : consommation conforme à la production
  M2  marche à vide  : tourne régulièrement sans produire
  M3  usure          : vibrations et courant qui augmentent peu à peu
  M4  pics           : surchauffes et pics de courant ponctuels

Une mesure = une minute de fonctionnement (SAMPLING_INTERVAL_HOURS = 1/60
côté service-carbone). Par défaut, une mesure est envoyée toutes les 2 s.

Usage :
    python simulator.py                      # broker localhost:1883
    MQTT_BROKER=mosquitto python simulator.py
    python simulator.py --interval 1 --count 200
"""
import argparse
import json
import math
import os
import random
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

TOPIC = "capteurs/mesures"


class Machine:
    def __init__(self, machine_id: str, scenario: str):
        self.machine_id = machine_id
        self.device_id = f"esp32-{machine_id.lower()}"
        self.scenario = scenario
        self.step = 0

    def next_measure(self) -> dict:
        self.step += 1
        t = self.step

        # Fonctionnement normal : 1 pièce par minute, ~27 A (≈ 0,093 kWh pour 0,1 attendu)
        production = 1
        courant = random.gauss(27, 0.8)
        temperature = random.gauss(45, 1.0)
        vibration = random.gauss(2.0, 0.15)
        pression = random.gauss(6.0, 0.1)

        if self.scenario == "idle":
            # 1 minute sur 3 : la machine tourne sans produire
            if t % 3 == 0:
                production = 0
                courant = random.gauss(12, 0.8)

        elif self.scenario == "wear":
            # Dérive lente : vibration et courant augmentent avec le temps
            drift = min(t / 150, 1.0)
            vibration = random.gauss(2.0 + 3.5 * drift, 0.15)
            courant = random.gauss(27 + 14 * drift, 0.8)
            temperature = random.gauss(45 + 10 * drift, 1.0)

        elif self.scenario == "spikes":
            # Environ 1 mesure sur 12 : surchauffe et pic de courant
            if random.random() < 0.08:
                courant = random.gauss(46, 2)
                temperature = random.gauss(85, 2)

        # Légère variation journalière commune
        temperature += 1.5 * math.sin(t / 30)

        return {
            "machine_id": self.machine_id,
            "device_id": self.device_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "courant": round(max(courant, 0), 2),
            "temperature": round(temperature, 2),
            "vibration": round(max(vibration, 0), 3),
            "pression": round(pression, 2),
            "debit": round(random.gauss(12, 0.5), 2),
            "production_count": production,
        }


MACHINES = [
    Machine("M1", "normal"),
    Machine("M2", "idle"),
    Machine("M3", "wear"),
    Machine("M4", "spikes"),
]


def connect(broker: str, port: int) -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="carbonghost-simulator")
    while True:
        try:
            client.connect(broker, port)
            client.loop_start()
            print(f"Connecté au broker MQTT {broker}:{port}", flush=True)
            return client
        except OSError as e:
            print(f"Broker MQTT indisponible ({e}), nouvel essai dans 3 s...", flush=True)
            time.sleep(3)


def main():
    parser = argparse.ArgumentParser(description="Simulateur de capteurs CarbonGhost")
    parser.add_argument("--broker", default=os.environ.get("MQTT_BROKER", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", 1883)))
    parser.add_argument("--interval", type=float, default=float(os.environ.get("SIM_INTERVAL", 2)),
                        help="secondes entre deux séries de mesures")
    parser.add_argument("--count", type=int, default=int(os.environ.get("SIM_COUNT", 0)),
                        help="nombre de séries à envoyer (0 = sans fin)")
    args = parser.parse_args()

    client = connect(args.broker, args.port)
    sent = 0
    try:
        while args.count == 0 or sent < args.count:
            for machine in MACHINES:
                payload = machine.next_measure()
                client.publish(TOPIC, json.dumps(payload), qos=1)
            sent += 1
            if sent % 10 == 0:
                print(f"{sent} séries envoyées ({sent * len(MACHINES)} mesures)", flush=True)
            time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
