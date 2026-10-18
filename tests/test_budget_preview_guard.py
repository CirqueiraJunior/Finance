"""Unit tests for preview authorization only; NOT PostgreSQL locking tests."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256

import pytest

from app.services.budget_preview_guard import (
    BudgetPreviewGuard, BudgetPreviewTokenError, canonical_sha256,
)


NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)
F = sha256(b"excel original").hexdigest()
G = sha256(b"excel diferente").hexdigest()
S = canonical_sha256([{"year": 2026, "value": "100.0000"}])
T = canonical_sha256([{"year": 2026, "value": "101.0000"}])


def guard():
    return BudgetPreviewGuard("x" * 48, ttl_seconds=120)


def test_valid_token_roundtrip():
    token = guard().issue(user_id=7, file_hash=F, state_hash=S, now=NOW)
    guard().verify(token, user_id=7, file_hash=F, state_hash=S, now=NOW)


@pytest.mark.parametrize("kwargs", [
    {"user_id": 8, "file_hash": F, "state_hash": S},
    {"user_id": 7, "file_hash": G, "state_hash": S},
    {"user_id": 7, "file_hash": F, "state_hash": T},
])
def test_changed_identity_file_or_state_rejected(kwargs):
    token = guard().issue(user_id=7, file_hash=F, state_hash=S, now=NOW)
    with pytest.raises(BudgetPreviewTokenError):
        guard().verify(token, now=NOW, **kwargs)


def test_expiration_rejected():
    token = guard().issue(user_id=7, file_hash=F, state_hash=S, now=NOW)
    with pytest.raises(BudgetPreviewTokenError):
        guard().verify(token, user_id=7, file_hash=F, state_hash=S,
                       now=NOW + timedelta(seconds=121))


def test_tampered_token_rejected():
    token = guard().issue(user_id=7, file_hash=F, state_hash=S, now=NOW)
    head, sig = token.split(".")
    tampered = head + "." + ("A" if sig[0] != "A" else "B") + sig[1:]
    with pytest.raises(BudgetPreviewTokenError):
        guard().verify(tampered, user_id=7, file_hash=F, state_hash=S, now=NOW)


def test_canonical_state_is_order_independent_for_keys():
    assert canonical_sha256({"b": 2, "a": 1}) == canonical_sha256({"a": 1, "b": 2})


def test_short_key_rejected():
    with pytest.raises(ValueError):
        BudgetPreviewGuard("weak")
