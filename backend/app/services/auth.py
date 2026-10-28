from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from backend.app.config import get_settings

password_hasher = PasswordHash.recommended()

ACCESS_TOKEN_MINUTES = 30
JWT_ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    return password_hasher.verify(password, password_hash)


def create_access_token(user_id: str, role: str) -> tuple[str, int]:
    expires_in = ACCESS_TOKEN_MINUTES * 60
    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=expires_in
    )

    payload = {
        "sub": user_id,
        "role": role,
        "exp": expires_at,
        "iat": datetime.now(timezone.utc),
    }

    token = jwt.encode(
        payload,
        get_settings().secret_key,
        algorithm=JWT_ALGORITHM,
    )

    return token, expires_in


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        get_settings().secret_key,
        algorithms=[JWT_ALGORITHM],
        options={"require": ["sub", "exp", "iat"]},
    )
