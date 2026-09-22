"""Protocolo de recuperação assistida exclusivo do Finance."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
import secrets

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from finance_server.models import AssistedRecoveryRequest, User


PRODUCT = "FINANCE"
PROTOCOL_VERSION = 1
PUBLIC_KEY_FINGERPRINT = (
    "E7EC128B1D4FFEDF1C9B39B914AC6B6FE113D9FF797EC019999908925743F548"
)
PUBLIC_KEY_PATH = Path(__file__).resolve().parent / "resources" / "recovery_public_key.pem"


class AssistedRecoveryError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ValidatedAuthorization:
    request: AssistedRecoveryRequest
    user: User


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _canonical(payload: dict) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def load_public_key() -> Ed25519PublicKey:
    try:
        key = serialization.load_pem_public_key(PUBLIC_KEY_PATH.read_bytes())
    except Exception as error:
        raise RuntimeError("Chave pública de recuperação do Finance inválida.") from error
    if not isinstance(key, Ed25519PublicKey):
        raise RuntimeError("Chave pública de recuperação do Finance inválida.")
    der = key.public_bytes(
        serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    if sha256(der).hexdigest().upper() != PUBLIC_KEY_FINGERPRINT:
        raise RuntimeError("Fingerprint da chave pública do Finance inválido.")
    return key


def create_request(
    db: Session,
    identifier: str,
    environment: str,
    validity_minutes: int,
) -> tuple[AssistedRecoveryRequest, str] | None:
    normalized = str(identifier or "").strip().casefold()
    user = db.scalar(
        select(User).where(
            or_(User.username.ilike(normalized), User.email.ilike(normalized)),
            User.ativo.is_(True),
        )
    )
    if user is None:
        return None
    now = datetime.now(timezone.utc)
    item = AssistedRecoveryRequest(
        request_id=secrets.token_urlsafe(48),
        user_id=user.id,
        environment=environment,
        expires_at=now + timedelta(minutes=validity_minutes),
    )
    db.add(item)
    db.flush()
    payload = {
        "v": PROTOCOL_VERSION,
        "product": PRODUCT,
        "environment": environment,
        "request_id": item.request_id,
        "user_id": user.id,
        "username": user.username,
        "created_at": now.isoformat(),
    }
    return item, _b64encode(_canonical(payload))


def validate_authorization(
    db: Session,
    authorization: str,
    environment: str,
) -> ValidatedAuthorization:
    token = str(authorization or "").strip()
    if token.count(".") != 1:
        raise AssistedRecoveryError("Código de autorização inválido.")
    payload_b64, signature_b64 = token.split(".", 1)
    try:
        payload_bytes = _b64decode(payload_b64)
        signature = _b64decode(signature_b64)
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception as error:
        raise AssistedRecoveryError("Código de autorização inválido.") from error
    try:
        load_public_key().verify(signature, payload_bytes)
    except InvalidSignature as error:
        raise AssistedRecoveryError("Assinatura da autorização inválida.") from error
    except RuntimeError:
        raise
    except Exception as error:
        raise AssistedRecoveryError("Código de autorização inválido.") from error

    required = {"v", "product", "environment", "request_id", "user_id", "exp"}
    if not required.issubset(payload):
        raise AssistedRecoveryError("Autorização Finance incompleta.")
    if payload["v"] != PROTOCOL_VERSION:
        raise AssistedRecoveryError("Versão da autorização não suportada.")
    if payload["product"] != PRODUCT:
        raise AssistedRecoveryError("A autorização não pertence ao Finance.")
    if payload["environment"] != environment:
        raise AssistedRecoveryError("A autorização pertence a outro ambiente.")
    try:
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=timezone.utc)
        user_id = int(payload["user_id"])
        request_id = str(payload["request_id"])
    except (TypeError, ValueError, OverflowError) as error:
        raise AssistedRecoveryError("Autorização Finance inválida.") from error
    now = datetime.now(timezone.utc)
    if expires_at <= now:
        raise AssistedRecoveryError("A autorização expirou.")

    item = db.scalar(
        select(AssistedRecoveryRequest)
        .where(AssistedRecoveryRequest.request_id == request_id)
        .with_for_update()
    )
    if item is None:
        raise AssistedRecoveryError("Solicitação de recuperação não localizada.")
    if item.used_at is not None:
        raise AssistedRecoveryError("Esta autorização já foi utilizada.")
    if _aware(item.expires_at) <= now:
        raise AssistedRecoveryError("A solicitação de recuperação expirou.")
    if item.environment != environment:
        raise AssistedRecoveryError("A solicitação pertence a outro ambiente.")
    if item.user_id != user_id:
        raise AssistedRecoveryError("A autorização não corresponde ao usuário.")
    user = db.get(User, item.user_id)
    if user is None or not user.ativo:
        raise AssistedRecoveryError("Usuário indisponível para recuperação.")
    return ValidatedAuthorization(item, user)
