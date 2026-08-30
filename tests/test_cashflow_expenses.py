from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import CashflowValidationError
from app.models.cashflow_entry import CashflowEntry
from app.repositories.cashflow_repository import CashflowRepository
from app.services.cashflow_service import CashflowService
from tests.boe_helpers import add_boe_import


@pytest.fixture
def service(db_session):
    return CashflowService(CashflowRepository(db_session))


def test_create_valid_expense(service):
    entry = service.create_expense(
        year=2026, month=7, entry_date=date(2026, 7, 20),
        description="Licença", category="ADMINISTRATIVO", value=Decimal("500.0000"),
    )
    assert entry.tipo == "DESPESA"
    assert entry.origem == "MANUAL"
    assert entry.categoria == "ADMINISTRATIVO"
    assert entry.boe_import_id is None
    assert entry.valor == Decimal("500.0000")


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_expense_rejects_non_positive_value(service, value):
    with pytest.raises(CashflowValidationError):
        service.create_expense(
            year=2026, month=7, entry_date=date(2026, 7, 1),
            description="Teste", category="ADMINISTRATIVO", value=value,
        )


def test_expense_rejects_blank_description(service):
    with pytest.raises(CashflowValidationError):
        service.create_expense(
            year=2026, month=7, entry_date=date(2026, 7, 1),
            description=" ", category="ADMINISTRATIVO", value=Decimal("1"),
        )


@pytest.mark.parametrize("category", ["INVALIDA", "RECEITA_DIRETA", "RECEITA_INDIRETA"])
def test_expense_rejects_invalid_or_revenue_category(service, category):
    with pytest.raises(CashflowValidationError):
        service.create_expense(
            year=2026, month=7, entry_date=date(2026, 7, 1),
            description="Teste", category=category, value=Decimal("1"),
        )


def test_database_rejects_expense_with_boe(db_session):
    boe = add_boe_import(db_session)
    entry = CashflowEntry(
        periodo_ano=2026, periodo_mes=7, data_lancamento=date(2026, 7, 1),
        descricao="Inválida", tipo="DESPESA", origem="BOE", categoria="ADMINISTRATIVO",
        valor=Decimal("1"), boe_import_id=boe.id,
    )
    db_session.add(entry)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_database_rejects_revenue_with_expense_category(db_session):
    entry = CashflowEntry(
        periodo_ano=2026, periodo_mes=7, data_lancamento=date(2026, 7, 1),
        descricao="Inválida", tipo="RECEITA", origem="MANUAL", categoria="ADMINISTRATIVO",
        valor=Decimal("1"), boe_import_id=None,
    )
    db_session.add(entry)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_expense_rejects_invalid_month(service):
    with pytest.raises(CashflowValidationError):
        service.create_expense(
            year=2026, month=13, entry_date=date(2026, 7, 1),
            description="Teste", category="ADMINISTRATIVO", value=Decimal("1"),
        )


def test_monthly_summary_uses_decimal(service, db_session):
    boe = add_boe_import(db_session)
    boe.valor_total = Decimal("21967.2684")
    db_session.commit()
    service.create_direct_revenue_from_boe(boe)
    service.create_indirect_revenue(
        year=2026, month=7, entry_date=date(2026, 7, 10),
        description="Indireta", value=Decimal("100.0000"),
    )
    service.create_expense(
        year=2026, month=7, entry_date=date(2026, 7, 20),
        description="Software", category="ADMINISTRATIVO", value=Decimal("500.0000"),
    )

    summary = service.get_monthly_summary(2026, 7)

    assert summary.direct_revenue == Decimal("21967.2684")
    assert summary.indirect_revenue == Decimal("100.0000")
    assert summary.total_revenue == Decimal("22067.2684")
    assert summary.total_expense == Decimal("500.0000")
    assert summary.monthly_balance == Decimal("21567.2684")
