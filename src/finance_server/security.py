from datetime import datetime, timedelta, timezone
from hashlib import sha256
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
import jwt


PASSWORD_HASHER = PasswordHasher()
PASSWORD_POLICY_MESSAGE = (
    "A senha deve possuir no mínimo 6 caracteres, incluindo uma letra maiúscula, "
    "uma letra minúscula e um número."
)


def validate_password(password: str) -> None:
    checks = (
        len(password) >= 6,
        any(character.isupper() for character in password),
        any(character.islower() for character in password),
        any(character.isdigit() for character in password),
    )
    if not all(checks):
        raise ValueError(PASSWORD_POLICY_MESSAGE)


def hash_password(password: str) -> str:
    validate_password(password)
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: int, role: str, secret_key: str, minutes: int) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "role": role, "type": "access",
                       "iat": now, "exp": now + timedelta(minutes=minutes)},
                      secret_key, algorithm="HS256")


def decode_access_token(token: str, secret_key: str) -> dict:
    payload = jwt.decode(token, secret_key, algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Tipo de token inválido")
    return payload


def random_token() -> str:
    return secrets.token_urlsafe(48)


def token_hash(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
