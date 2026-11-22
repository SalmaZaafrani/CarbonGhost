import logging
import unicodedata

from domain.safety_policy import SafetyPolicy
from application.prompts.assistant_prompts import SYSTEM_PROMPT, build_ask_prompt, CAUSE_LABELS

log = logging.getLogger("service-assistant")

# Mots-clés reconnus par le mode sans IA (sans accents, en minuscules)
INTENTS = [
    ("co2",      ("co2", "carbone", "emission", "eviter", "evitable", "combien", "kwh", "energie", "gaspille")),
    ("wear",     ("usure", "vibration", "roulement", "maintenance", "panne", "inspection", "abime")),
    ("action",   ("priorite", "faire", "action", "recommand", "conseil", "dois", "solution", "ameliorer", "reduire")),
    ("status",   ("normal", "fonctionne", "etat", "sante", "marche bien", "probleme")),
    ("cause",    ("pourquoi", "cause", "raison", "consomme", "trop", "surconsommation", "explique")),
]


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


def _detect_intent(question: str) -> str:
    q = _normalize(question)
    for intent, keywords in INTENTS:
        if any(k in q for k in keywords):
            return intent
    return "summary"


class AskAssistantUseCase:
    def __init__(self, repository, llm_client):
        self.repository = repository
        self.llm_client = llm_client

    async def execute(self, machine_id: str, question: str) -> str:
        SafetyPolicy.validate_question(question)
        context = self.repository.get_context_for_llm(machine_id)
        if not context:
            return f"Je n'ai encore aucune donnée pour la machine {machine_id}."

        if not self.llm_client.available:
            return self._answer_without_llm(question, context)

        prompt = build_ask_prompt(question, context)
        try:
            response = await self.llm_client.generate(system_prompt=SYSTEM_PROMPT, user_prompt=prompt)
        except Exception as e:  # IA indisponible : on répond quand même à partir des données
            log.error("Échec de l'appel au LLM, réponse sans IA : %s", e)
            return self._answer_without_llm(question, context)
        SafetyPolicy.validate_response(response)
        return response

    # ─────────────── Mode sans IA : réponse selon le sujet de la question ───────────────

    @staticmethod
    def _answer_without_llm(question: str, c: dict) -> str:
        m = c["machine_id"]
        n, waste = c["events_analyzed"], c["waste_events"]
        causes = c["main_causes"]
        main_cause = causes[0][0] if causes else None
        label = lambda k: CAUSE_LABELS.get(k, k)
        intent = _detect_intent(question)

        if intent == "co2":
            if waste == 0:
                return (f"Sur les {n} dernières mesures, {m} n'a presque rien gaspillé : "
                        f"{c['avoidable_co2_kg']} kg de CO2 évitable seulement ({c['wasted_kwh']} kWh).")
            return (f"Sur les {n} dernières mesures, {m} a gaspillé {c['wasted_kwh']} kWh, "
                    f"soit {c['avoidable_co2_kg']} kg de CO2 qui auraient pu être évités.\n"
                    f"L'essentiel vient de : {label(main_cause)} ({causes[0][1]} fois).")

        if intent == "wear":
            wear = dict(causes).get("usure_mecanique", 0)
            if wear == 0:
                return f"Aucun signe d'usure mécanique sur {m} : les vibrations restent normales sur les {n} dernières mesures."
            return (f"Oui : {wear} mesures sur {n} montrent des vibrations élevées avec une surconsommation sur {m}.\n"
                    f"Recommandation : {c['recommendations'].get('usure_mecanique')}")

        if intent == "action":
            if waste == 0:
                return f"Rien d'urgent sur {m} : la consommation est conforme à la production. Continuez la surveillance habituelle."
            lines = [f"Actions prioritaires pour {m}, par ordre d'importance :"]
            for i, (cause, count) in enumerate(causes[:3], 1):
                lines.append(f"{i}. {c['recommendations'].get(cause)} ({label(cause)}, {count} fois)")
            return "\n".join(lines)

        if intent == "status":
            if waste == 0:
                return f"Oui, {m} fonctionne normalement : aucun gaspillage sur les {n} dernières mesures."
            ratio = round(waste / n * 100)
            return (f"Non, {m} présente un problème : {waste} gaspillages sur {n} mesures ({ratio} %).\n"
                    f"Cause la plus fréquente : {label(main_cause)}.")

        if intent == "cause":
            if waste == 0:
                return (f"{m} ne consomme pas trop : dernière mesure {c['actual_energy']} kWh pour "
                        f"{c['expected_energy']} kWh attendus, et aucun gaspillage sur les {n} dernières mesures.")
            explication = ", ".join(f"{label(k)} ({v} fois)" for k, v in causes[:3])
            return (f"{m} consomme trop à cause de : {explication}.\n"
                    f"Cause principale : {label(main_cause)}.\n"
                    f"Recommandation : {c['recommendations'].get(main_cause)}")

        # Résumé par défaut
        lines = [
            f"Machine {m} — dernière mesure : {c['actual_energy']} kWh consommés pour {c['expected_energy']} kWh attendus"
            + (f" (écart {c['deviation_pct']} %)." if c.get("deviation_pct") is not None else "."),
            f"Cause probable : {label(c['probable_cause'])}.",
            f"Recommandation : {c['recommendation']}",
            f"Sur les {n} dernières mesures : {waste} gaspillages détectés, {c['avoidable_co2_kg']} kg de CO2 évitable.",
        ]
        if causes:
            lines.append("Causes les plus fréquentes : " + ", ".join(f"{label(k)} ({v})" for k, v in causes[:3]) + ".")
        return "\n".join(lines)
