"""Canonical budget import snapshot for signed preview authorizations.

No database writes. Includes imported values and existing persisted state.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.budget_preview_guard import canonical_sha256


def _money(value: Any) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.0001")), ".4f")


def budget_snapshot(validation: Any, existing: dict) -> str:
    """Fingerprint the *entire* reviewed import and impacted persisted records.

    A missing row has a distinct state; descriptions and notes are included.
    The caller must collect the state in a transaction with appropriate locks
    when checking at commit time.
    """
    records = []
    for row in validation.preview:
        key = (row.year, row.month, row.entry_type, row.category)
        old = existing.get(key)
        records.append({
            "key": [row.year, row.month, row.entry_type, row.category],
            "incoming": {
                "value": _money(row.value),
                "description": row.source_label,
            },
            "existing": None if old is None else {
                "id": int(old.id),
                "value": _money(old.valor_orcado),
                "description": old.descricao,
                "notes": old.observacao,
            },
        })
    records.sort(key=lambda item: tuple(item["key"]))
    return canonical_sha256(records)
