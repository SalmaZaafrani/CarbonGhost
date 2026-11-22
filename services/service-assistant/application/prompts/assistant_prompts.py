SYSTEM_PROMPT = """Tu es l'assistant technique de CarbonGhost Sentinel.
Tu expliques aux operateurs les anomalies de consommation energetique et carbone.
Tu ne dois jamais donner d'instructions de controle machine, ni reveler de secrets techniques (certificats, cles, identifiants).
Reponds de facon claire, concise, et orientee action pour un operateur d'usine."""


def build_ask_prompt(question: str, context: dict) -> str:
    return f"""Contexte machine :
- Machine : {context.get('machine_id')}
- Consommation attendue : {context.get('expected_energy')} kWh
- Consommation mesuree : {context.get('actual_energy')} kWh
- Ecart : {context.get('deviation_pct')}%
- Cause probable : {context.get('probable_cause')}
- Recommandation existante : {context.get('recommendation')}
- Sur les {context.get('events_analyzed')} dernieres mesures : {context.get('waste_events')} gaspillages, {context.get('avoidable_co2_kg')} kg de CO2 evitable
- Causes les plus frequentes : {context.get('main_causes')}

Question de l'operateur : {question}
"""


CAUSE_LABELS = {
    "aucune": "aucune anomalie de consommation",
    "fonctionnement_a_vide": "la machine tourne à vide (consomme sans produire)",
    "usure_mecanique": "usure mécanique (vibrations élevées)",
    "surchauffe": "surchauffe",
    "fuite_pneumatique": "fuite pneumatique (pression basse)",
    "reglage_non_optimal": "réglage non optimal",
    "unknown": "inconnue",
}
