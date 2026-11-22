import logging

from config import settings

log = logging.getLogger("service-assistant")

# Modèles à exclure du choix automatique (audio, modération, etc.)
_NOT_CHAT = ("whisper", "guard", "tts", "embed", "distil", "playai", "orpheus", "prompt")
# Préférences, de la plus souhaitée à la moins souhaitée
_PREFERRED = ("llama-3.3", "gpt-oss-120b", "llama-4", "gpt-oss", "qwen", "llama", "kimi", "gemma", "mistral")


class GroqAssistantClient:
    """
    Client LLM (Groq). `available` est faux si aucune clé n'est configurée.

    Si le modèle configuré (GROQ_MODEL) n'existe plus chez Groq, un modèle de
    chat disponible est choisi automatiquement dans la liste du compte.
    """

    def __init__(self):
        self.available = bool(settings.groq_api_key.strip())
        self.model = settings.groq_model
        self.client = None
        if self.available:
            from groq import AsyncGroq
            self.client = AsyncGroq(api_key=settings.groq_api_key)

    async def _pick_available_model(self) -> str | None:
        models = await self.client.models.list()
        ids = [m.id for m in models.data if not any(x in m.id.lower() for x in _NOT_CHAT)]
        for pref in _PREFERRED:
            for model_id in sorted(ids):
                if pref in model_id.lower():
                    return model_id
        return ids[0] if ids else None

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        if not self.available:
            raise RuntimeError("Aucune clé GROQ_API_KEY configurée")
        from groq import NotFoundError

        try:
            return await self._complete(system_prompt, user_prompt)
        except NotFoundError:
            new_model = await self._pick_available_model()
            if not new_model or new_model == self.model:
                raise
            log.warning("Modèle %s indisponible chez Groq, utilisation de %s", self.model, new_model)
            self.model = new_model
            return await self._complete(system_prompt, user_prompt)

    async def _complete(self, system_prompt: str, user_prompt: str) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            temperature=0.2,
            max_tokens=1000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        return response.choices[0].message.content or ""
