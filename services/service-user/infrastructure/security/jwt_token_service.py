from datetime import datetime, timedelta, timezone

import jwt

from application.ports.token_service import ITokenService


class JwtTokenService(ITokenService):
    def __init__(self, secret: str, expiration_minutes: int = 60):
        self.secret = secret
        self.expiration_minutes = expiration_minutes

    def generate_token(self, data: dict) -> str:
        payload = {**data, "exp": datetime.now(timezone.utc) + timedelta(minutes=self.expiration_minutes)}
        return jwt.encode(payload, self.secret, algorithm="HS256")

    def verify_token(self, token: str) -> dict:
        return jwt.decode(token, self.secret, algorithms=["HS256"])
