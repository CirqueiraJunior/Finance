"""Canonical budget import snapshot for signed preview authorizations.

No database writes. Includes imported values and existing persisted state.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.services.budget_preview_guard import canonical_sha256
from app.repositories.budget_repository import BudgetRepository


def _money(value: Any) -> str:
    return format(Decimal(str(value)).quantize(Decimal("0.0001")), ".4f")


def budget_snapshot(
    validation: Any,
    existing: dict,
    scoped_entries: Any = (),
) -> str:
    """Fingerprint the *entire* reviewed import and impacted persisted records.

    A missing row has a distinct state; descriptions and notes are included.
    The caller must collect the state in a transaction with appropriate locks
    when checking at commit time.
    """
    records = []
    for row in validation.preview:
        key = (
            row.year, row.month, row.entry_type, row.category,
            BudgetRepository.description_key(row.source_label),
        )
        old = existing.get(key)
        records.append({
            "key": list(key),
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

    groups = {
        (row.year, row.month, row.entry_type, row.category)
        for row in validation.preview
    }
    scope = []
    for entry in scoped_entries:
        group = (
            entry.periodo_ano, entry.periodo_mes,
            entry.tipo, entry.categoria,
        )
        if group not in groups:
            continue
        scope.append({
            "id": int(entry.id),
            "key": [
                *group,
                BudgetRepository.description_key(entry.descricao),
            ],
            "value": _money(entry.valor_orcado),
            "description": entry.descricao,
            "notes": entry.observacao,
        })
    scope.sort(key=lambda item: (tuple(item["key"]), item["id"]))

    return canonical_sha256({
        "incoming_and_matches": records,
        "persisted_scope": scope,
    })
