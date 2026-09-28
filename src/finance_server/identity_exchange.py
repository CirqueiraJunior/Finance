"""Control Center identity-proof verification for Finance Server."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


EXPECTED_VERSION = 1
EXPECTED_ALGORITHM = "Ed25519"
EXPECTED_ISSUER = "ja-technology-control-center"
EXPECTED_AUDIENCE = "finance"

PROOF_TTL = timedelta(seconds=90)
CLOCK_SKEW = timedelta(seconds=5)


class IdentityExchangeError(ValueError):
    """Raised when one Control Center identity proof is rejected."""


@dataclass(frozen=True, slots=True)
class VerifiedIdentity:
    sub: str
    name: str
    email: str
    sid: str
    jti: str
    nonce: str


def verify_identity_envelope(
    envelope_text: str,
    *,
    trusted_kid: str,
    trusted_public_key: bytes,
    expected_nonce: str,
    now: datetime | None = None,
) -> VerifiedIdentity:
    """Verify one Control Center proof without importing Control Center code."""

    try:
        document = json.loads(envelope_text)
    except (TypeError, json.JSONDecodeError) as error:
        raise IdentityExchangeError("Prova de identidade inválida.") from error

    if not isinstance(document, dict):
        raise IdentityExchangeError("Prova de identidade inválida.")

    if set(document) != {"alg", "kid", "payload", "signature", "v"}:
        raise IdentityExchangeError("Prova de identidade inválida.")

    if document.get("v") != EXPECTED_VERSION:
        raise IdentityExchangeError("Versão da prova de identidade não suportada.")

    if document.get("alg") != EXPECTED_ALGORITHM:
        raise IdentityExchangeError("Algoritmo da prova de identidade não suportado.")

    if document.get("kid") != trusted_kid:
        raise IdentityExchangeError("Chave de assinatura não confiável.")

    try:
        payload = base64.b64decode(document["payload"], validate=True)
        signature = base64.b64decode(document["signature"], validate=True)
    except (KeyError, TypeError, ValueError) as error:
        raise IdentityExchangeError("Prova de identidade inválida.") from error

    if len(trusted_public_key) != 32 or len(signature) != 64:
        raise IdentityExchangeError("Material criptográfico inválido.")

    try:
        Ed25519PublicKey.from_public_bytes(trusted_public_key).verify(
            signature,
            payload,
        )
    except (InvalidSignature, ValueError) as error:
        raise IdentityExchangeError("Assinatura da prova de identidade inválida.") from error

    try:
        claims = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IdentityExchangeError("Payload da prova de identidade inválido.") from error

    expected_claims = {
        "active",
        "aud",
        "email",
        "exp",
        "iat",
        "iss",
        "jti",
        "name",
        "nonce",
        "product_access",
        "sid",
        "sub",
    }

    if not isinstance(claims, dict) or set(claims) != expected_claims:
        raise IdentityExchangeError("Claims da prova de identidade inválidos.")

    if claims["iss"] != EXPECTED_ISSUER:
        raise IdentityExchangeError("Emissor da prova de identidade inválido.")

    if claims["aud"] != EXPECTED_AUDIENCE:
        raise IdentityExchangeError("Audiência da prova de identidade inválida.")

    if claims["active"] is not True:
        raise IdentityExchangeError("Identidade central inativa.")

    product_access = claims["product_access"]

    if (
        not isinstance(product_access, list)
        or EXPECTED_AUDIENCE not in product_access
    ):
        raise IdentityExchangeError("Identidade sem acesso ao Finance.")

    if claims["nonce"] != expected_nonce:
        raise IdentityExchangeError("Challenge da prova de identidade inválido.")

    email = claims["email"]

    if not isinstance(email, str) or not email.strip():
        raise IdentityExchangeError(
            "A identidade central não possui e-mail para vínculo com o Finance."
        )

    issued_at = _parse_datetime(claims["iat"], "iat")
    expires_at = _parse_datetime(claims["exp"], "exp")

    if expires_at - issued_at != PROOF_TTL:
        raise IdentityExchangeError("TTL da prova de identidade inválido.")

    current = now or datetime.now(timezone.utc)

    if current < issued_at - CLOCK_SKEW:
        raise IdentityExchangeError("Prova de identidade ainda não é válida.")

    if current >= expires_at + CLOCK_SKEW:
        raise IdentityExchangeError("Prova de identidade expirada.")

    for field in ("sub", "name", "sid", "jti", "nonce"):
        if not isinstance(claims[field], str) or not claims[field].strip():
            raise IdentityExchangeError(
                f"Claim obrigatório inválido: {field}."
            )

    return VerifiedIdentity(
        sub=claims["sub"],
        name=claims["name"],
        email=email.strip().casefold(),
        sid=claims["sid"],
        jti=claims["jti"],
        nonce=claims["nonce"],
    )


def decode_public_key_b64(value: str) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (TypeError, ValueError) as error:
        raise IdentityExchangeError(
            "Chave pública do Control Center inválida."
        ) from error

    if len(decoded) != 32:
        raise IdentityExchangeError(
            "Chave pública Ed25519 deve possuir 32 bytes."
        )

    return decoded


def _parse_datetime(value: object, field_name: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise IdentityExchangeError(
            f"Claim de data inválido: {field_name}."
        )

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise IdentityExchangeError(
            f"Claim de data inválido: {field_name}."
        ) from error

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise IdentityExchangeError(
            f"Claim de data inválido: {field_name}."
        )

    return parsed.astimezone(timezone.utc)
