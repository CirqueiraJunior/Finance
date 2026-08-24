from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.cashflow_entry import CashflowEntry
from tests.boe_helpers import add_boe_import
from tests.cashflow_helpers import make_manual_entry


def test_cashflow_entry_persists_decimal(db_session):
    entry = make_manual_entry()
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    assert entry.valor == Decimal("100.1234")
    assert entry.boe_import_id is None


def test_cashflow_entry_relationship_with_boe(db_session):
    boe_import = add_boe_import(db_session)
    entry = CashflowEntry(
        periodo_ano=2026, periodo_mes=7, data_lancamento=date(2026, 7, 1),
        descricao="Receita Direta BOE 07/2026", tipo="RECEITA", origem="BOE",
        categoria="RECEITA_DIRETA", valor=Decimal("21967.2684"),
        boe_import_id=boe_import.id,
    )
    db_session.add(entry)
    db_session.commit()

    assert entry.boe_import is boe_import
    assert boe_import.cashflow_entry is entry


def test_boe_import_id_is_unique(db_session):
    boe_import = add_boe_import(db_session)
    first = CashflowEntry(
        periodo_ano=2026, periodo_mes=7, data_lancamento=date(2026, 7, 1),
        descricao="Primeiro", tipo="RECEITA", origem="BOE",
        categoria="RECEITA_DIRETA", valor=Decimal("1"), boe_import_id=boe_import.id,
    )
    second = CashflowEntry(
        periodo_ano=2026, periodo_mes=7, data_lancamento=date(2026, 7, 1),
        descricao="Segundo", tipo="RECEITA", origem="BOE",
        categoria="RECEITA_DIRETA", valor=Decimal("1"), boe_import_id=boe_import.id,
    )
    db_session.add(first)
    db_session.commit()
    db_session.add(second)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_database_rejects_incoherent_manual_boe_link(db_session):
    boe_import = add_boe_import(db_session)
    entry = make_manual_entry()
    entry.boe_import_id = boe_import.id
    db_session.add(entry)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
