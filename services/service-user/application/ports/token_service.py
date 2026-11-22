from abc import ABC, abstractmethod


class ITokenService(ABC):
    """Port d'interface pour la gestion des tokens de sécurité."""

    @abstractmethod
    def generate_token(self, data: dict) -> str:
        """Génère un token à partir d'un dictionnaire de données."""

    @abstractmethod
    def verify_token(self, token: str) -> dict:
        """Vérifie un token et renvoie son contenu. Lève une exception s'il est invalide ou expiré."""
