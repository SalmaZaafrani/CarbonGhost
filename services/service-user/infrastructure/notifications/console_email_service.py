import logging

from application.ports.email_notification_service import IEmailNotificationService

log = logging.getLogger("service-user")


class ConsoleEmailNotificationService(IEmailNotificationService):
    """Adaptateur de développement : écrit les emails dans les logs au lieu de les envoyer."""

    def send_welcome_email(self, to: str, username: str) -> None:
        log.warning("[email] Bienvenue %s <%s>", username, to)

    def send_password_reset_email(self, to: str, reset_link: str) -> None:
        log.warning("[email] Réinitialisation du mot de passe pour %s : %s", to, reset_link)
