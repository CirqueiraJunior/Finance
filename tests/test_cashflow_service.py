from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import CashflowDuplicateBOEError, CashflowValidationError
from app.repositories.cashflow_repository import CashflowRepository
from app.services.cashflow_service import CashflowService
from tests.boe_helpers import add_boe_import


@pytest.fixture
def service(db_session):
    return CashflowService(CashflowRepository(db_session))


def test_create_direct_revenue_from_imported_boe(service, db_session):
    boe_import = add_boe_import(db_session)
    boe_import.valor_total = Decimal("21967.2684")
    db_session.commit()

    entry = service.create_direct_revenue_from_boe(boe_import)

    assert (entry.periodo_ano, entry.periodo_mes) == (2026, 7)
    assert entry.valor == Decimal("21967.2684")
    assert entry.origem == "BOE"
    assert entry.categoria == "RECEITA_DIRETA"


def test_direct_revenue_duplicate_is_blocked(service, db_session):
    boe_import = add_boe_import(db_session)
    boe_import.valor_total = Decimal("1.0000")
    db_session.commit()
    service.create_direct_revenue_from_boe(boe_import)
    with pytest.raises(CashflowDuplicateBOEError):
        service.create_direct_revenue_from_boe(boe_import)


def test_non_imported_boe_is_blocked(service, db_session):
    boe_import = add_boe_import(db_session)
    boe_import.status = "validated"
    db_session.commit()
    with pytest.raises(CashflowValidationError):
        service.create_direct_revenue_from_boe(boe_import)


def test_create_indirect_revenue(service):
    entry = service.create_indirect_revenue(
        year=2026, month=7, entry_date=date(2026, 7, 20),
        description="Receita controlada", value=Decimal("150.4321"), notes="Teste",
    )
    assert entry.origem == "MANUAL"
    assert entry.categoria == "RECEITA_INDIRETA"
    assert entry.boe_import_id is None


@pytest.mark.parametrize("month", [0, 13])
def test_indirect_revenue_rejects_invalid_month(service, month):
    with pytest.raises(CashflowValidationError):
        service.create_indirect_revenue(
            year=2026, month=month, entry_date=date(2026, 7, 1),
            description="Teste", value=Decimal("1"),
        )


@pytest.mark.parametrize("value", [Decimal("0"), Decimal("-1")])
def test_indirect_revenue_rejects_non_positive_value(service, value):
    with pytest.raises(CashflowValidationError):
        service.create_indirect_revenue(
            year=2026, month=7, entry_date=date(2026, 7, 1),
            description="Teste", value=value,
        )


def test_indirect_revenue_rejects_blank_description(service):
    with pytest.raises(CashflowValidationError):
        service.create_indirect_revenue(
            year=2026, month=7, entry_date=date(2026, 7, 1),
            description="  ", value=Decimal("1"),
        )
