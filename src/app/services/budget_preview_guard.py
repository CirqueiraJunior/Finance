"""Signed, expiring authorization for budget import previews.

Pure Python: no DB access, UI imports or network operations.
A token binds a user, a file hash and a snapshot hash.
Not a replay-prevention mechanism: server-side transaction enforcement remains required.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
from hashlib import sha256
import hmac
import json
from pathlib import Path
import secrets
from typing import Any


class BudgetPreviewTokenError(ValueError):
    """A preview authorization is invalid, expired or does not match."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    if not isinstance(data, str) or len(data) > 16384:
        raise BudgetPreviewTokenError("Autorização inválida.")
    try:
        return base64.b64decode(
            data + "=" * (-len(data) % 4), altchars=b"-_", validate=True
        )
    except Exception as exc:
        raise BudgetPreviewTokenError("Autorização inválida.") from exc


def file_sha256(path: str | Path) -> str:
    result = sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def canonical_sha256(snapshot: Any) -> str:
    """Hash deterministic JSON from caller-normalized DB/import records.

    Caller MUST convert Decimal to fixed-precision strings before passing
    state, and MUST include every attribute affected by an import.
    """
    payload = json.dumps(
        snapshot, sort_keys=True, ensure_ascii=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    return sha256(payload).hexdigest()


class BudgetPreviewGuard:
    def __init__(self, secret: str, *, ttl_seconds: int = 600) -> None:
        if not isinstance(secret, str) or len(secret.encode("utf-8")) < 32:
            raise ValueError("Segredo do servidor insuficiente para autorizar prévias.")
        if not 1 <= ttl_seconds <= 3600:
            raise ValueError("Prazo da autorização inválido.")
        self._key = hmac.new(
            secret.encode("utf-8"), b"finance:budget-import-preview:v1",
            sha256,
        ).digest()
        self.ttl_seconds = ttl_seconds

    def issue(
        self, *, user_id: int, file_hash: str, state_hash: str,
        now: datetime | None = None,
    ) -> str:
        self._validate_inputs(user_id, file_hash, state_hash)
        timestamp = self._timestamp(now)
        claims = {
            "v": 1, "uid": user_id, "file": file_hash, "state": state_hash,
            "iat": timestamp, "exp": timestamp + self.ttl_seconds,
            "jti": secrets.token_hex(12),
        }
        content = _b64(json.dumps(
            claims, sort_keys=True, separators=(",", ":")
        ).encode("utf-8"))
        signature = _b64(hmac.new(self._key, content.encode("ascii"), sha256).digest())
        return f"{content}.{signature}"

    def verify(
        self, token: str, *, user_id: int, file_hash: str,
        state_hash: str, now: datetime | None = None,
    ) -> None:
        self._validate_inputs(user_id, file_hash, state_hash)
        if not isinstance(token, str) or token.count(".") != 1:
            raise BudgetPreviewTokenError("Autorização inválida.")
        content, signature = token.split(".")
        expected = _b64(
            hmac.new(self._key, content.encode("ascii"), sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            raise BudgetPreviewTokenError("Assinatura da autorização inválida.")
        try:
            claims = json.loads(_unb64(content))
        except (UnicodeError, ValueError, TypeError) as exc:
            raise BudgetPreviewTokenError("Autorização inválida.") from exc
        clock = self._timestamp(now)
        if (
            not isinstance(claims, dict)
            or type(claims.get("v")) is not int or claims["v"] != 1
            or type(claims.get("uid")) is not int or claims["uid"] != user_id
            or type(claims.get("iat")) is not int
            or type(claims.get("exp")) is not int
            or not isinstance(claims.get("jti"), str)
            or len(claims["jti"]) != 24
            or claims["iat"] > clock + 30
            or claims["exp"] <= clock
            or claims["exp"] - claims["iat"] != self.ttl_seconds
        ):
            raise BudgetPreviewTokenError("Autorização inválida ou expirada.")
        if not hmac.compare_digest(str(claims.get("file")), file_hash):
            raise BudgetPreviewTokenError("Arquivo diferente da prévia autorizada.")
        if not hmac.compare_digest(str(claims.get("state")), state_hash):
            raise BudgetPreviewTokenError("Dados alterados desde a validação.")

    @staticmethod
    def _timestamp(now: datetime | None) -> int:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("Data precisa incluir fuso horário.")
        return int(current.timestamp())

    @staticmethod
    def _validate_inputs(user_id: int, file_hash: str, state_hash: str) -> None:
        if type(user_id) is not int or user_id <= 0:
            raise ValueError("Usuário inválido.")
        for digest in (file_hash, state_hash):
            if (not isinstance(digest, str) or len(digest) != 64
                    or any(ch not in "0123456789abcdef" for ch in digest)):
                raise ValueError("Hash SHA-256 inválido.")
