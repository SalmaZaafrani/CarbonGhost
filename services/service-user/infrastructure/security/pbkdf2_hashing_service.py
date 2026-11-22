import base64
import hashlib
import hmac
import os

from application.ports.hashing_service import IHashingService


class Pbkdf2HashingService(IHashingService):
    """Hachage PBKDF2-SHA256 avec sel aléatoire (bibliothèque standard Python)."""

    ITERATIONS = 310_000

    def hash_password(self, password: str) -> str:
        salt = os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, self.ITERATIONS)
        return f"pbkdf2_sha256${self.ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"

    def verify_password(self, password: str, hashed_password: str) -> bool:
        try:
            _, iterations, salt, digest = hashed_password.split("$")
            expected = base64.b64decode(digest)
            computed = hashlib.pbkdf2_hmac("sha256", password.encode(), base64.b64decode(salt), int(iterations))
            return hmac.compare_digest(expected, computed)
        except (ValueError, TypeError):
            return False
