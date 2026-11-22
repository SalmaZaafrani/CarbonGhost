from collections import defaultdict
from datetime import datetime, timedelta, timezone

from application.prompts.assistant_prompts import CAUSE_LABELS
from domain.ports.repositories.i_carbon_event_repository import ICarbonEventRepository

SYSTEM_PROMPT = """
Tu es un assistant specialise dans le monitoring energetique et carbone d'une usine.
Genere un rapport professionnel en francais.
Le rapport doit contenir :
1. Resume general
2. Nombre d'evenements
3. Machines concernees
4. Evenements importants
5. Recommandations
Ne cree aucune donnee qui n'existe pas.
"""


class GenerateReportUseCase:
    def __init__(self, repository: ICarbonEventRepository, llm):
        self.repository = repository
        self.llm = llm

    async def execute(self, hours: int = 24) -> str:
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        events = self.repository.get_events_between(start=start, end=end)
        stats = self._stats(events)

        if not events:
            return f"Aucun événement carbone sur les {hours} dernières heures."
        if not self.llm.available:
            return self._report_without_llm(hours, len(events), stats)

        user_prompt = f"Periode analysee : de {start:%d/%m/%Y %H:%M} a {end:%d/%m/%Y %H:%M} (UTC)\n\n" \
                      f"Statistiques par machine :\n{self._stats_text(stats)}"
        try:
            return await self.llm.generate(system_prompt=SYSTEM_PROMPT, user_prompt=user_prompt)
        except Exception:  # IA indisponible : rapport construit à partir des données
            return self._report_without_llm(hours, len(events), stats)

    @staticmethod
    def _stats(events):
        stats = defaultdict(lambda: {"events": 0, "waste": 0, "co2": 0.0, "actual": 0.0,
                                     "expected": 0.0, "causes": defaultdict(int), "reco": {}})
        for e in events:
            s = stats[e.machine_id]
            s["events"] += 1
            s["co2"] += e.avoidable_co2_kg or 0
            s["actual"] += e.actual_energy_kwh or 0
            s["expected"] += e.expected_energy_kwh or 0
            if e.status == "waste_detected":
                s["waste"] += 1
                s["causes"][e.probable_cause] += 1
                s["reco"][e.probable_cause] = e.recommendation
        return dict(sorted(stats.items()))

    @staticmethod
    def _stats_text(stats) -> str:
        lines = []
        for machine, s in stats.items():
            causes = ", ".join(f"{k} ({n})" for k, n in sorted(s["causes"].items(), key=lambda kv: -kv[1]))
            lines.append(
                f"- {machine} : {s['events']} mesures, {s['waste']} gaspillages, "
                f"{s['actual']:.3f} kWh consommes pour {s['expected']:.3f} attendus, "
                f"{s['co2']:.3f} kg CO2 evitable. Causes : {causes or 'aucune'}"
            )
        return "\n".join(lines)

    @staticmethod
    def _report_without_llm(hours, n_events, stats) -> str:
        total_co2 = sum(s["co2"] for s in stats.values())
        lines = [
            f"Rapport des {hours} dernières heures",
            f"{n_events} mesures analysées sur {len(stats)} machines — {total_co2:.3f} kg de CO2 évitable au total.",
            "",
        ]
        for machine, s in sorted(stats.items(), key=lambda kv: -kv[1]["co2"]):
            lines.append(f"• {machine} : {s['waste']} gaspillages sur {s['events']} mesures, {s['co2']:.3f} kg CO2 évitable.")
            if s["causes"]:
                main = max(s["causes"], key=s["causes"].get)
                lines.append(f"  Cause principale : {CAUSE_LABELS.get(main, main)}. {s['reco'].get(main, '')}")
        return "\n".join(lines)
