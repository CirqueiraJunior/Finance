"""Chaves pessoais de recuperação: o segredo existe somente na resposta atual."""

from datetime import datetime, timezone
from hashlib import sha256
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from finance_server.models import PersonalRecoveryKey, User


class PersonalRecoveryError(ValueError):
    pass


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def revoke_active_keys(db: Session, user: User) -> None:
    now = datetime.now(timezone.utc)
    for item in db.scalars(
        select(PersonalRecoveryKey).where(
            PersonalRecoveryKey.user_id == user.id,
            PersonalRecoveryKey.used_at.is_(None),
            PersonalRecoveryKey.revoked_at.is_(None),
        )
    ):
        item.revoked_at = now


def generate_key(db: Session, user: User) -> tuple[str, PersonalRecoveryKey]:
    revoke_active_keys(db, user)
    raw = f"FIN-{secrets.token_urlsafe(32)}"
    item = PersonalRecoveryKey(user_id=user.id, key_hash=_digest(raw))
    db.add(item)
    db.flush()
    return raw, item


def validate_key(db: Session, user: User, raw_key: str) -> PersonalRecoveryKey:
    supplied = _digest(raw_key.strip())
    candidates = db.scalars(
        select(PersonalRecoveryKey).where(
            PersonalRecoveryKey.user_id == user.id,
            PersonalRecoveryKey.used_at.is_(None),
            PersonalRecoveryKey.revoked_at.is_(None),
        )
    )
    for item in candidates:
        if secrets.compare_digest(item.key_hash, supplied):
            return item
    raise PersonalRecoveryError("Chave pessoal de recuperação inválida ou já utilizada.")
