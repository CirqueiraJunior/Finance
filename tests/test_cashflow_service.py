from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import CashflowDuplicateBOEError, CashflowValidationError
from app.models.cashflow_entry import CashflowEntry
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

    assert (entry.periodo_ano, entry.periodo_mes) == (2026, 8)
    assert entry.valor == Decimal("21967.2684")
    assert entry.origem == "BOE"
    assert entry.categoria == "RECEITA_DIRETA"


def test_direct_revenue_competence_crosses_year(service, db_session):
    boe_import = add_boe_import(db_session, year=2025, month=12)
    boe_import.valor_total = Decimal("100.0000")
    db_session.commit()

    entry = service.create_direct_revenue_from_boe(boe_import)

    assert (entry.periodo_ano, entry.periodo_mes) == (2026, 1)
    assert service.get_monthly_summary(2026, 1).direct_revenue == Decimal("100.0000")


def test_summary_derives_previous_boe_without_duplicating_materialized_entry(
    service, db_session,
):
    april = add_boe_import(db_session, month=4)
    april.valor_total = Decimal("4857.9200")
    db_session.commit()
    service.create_direct_revenue_from_boe(april)

    may = service.get_monthly_summary(2026, 5)

    assert may.direct_revenue == Decimal("4857.9200")
    assert may.direct_revenue_available is True


def test_june_direct_revenue_comes_from_may_boe(service, db_session):
    may = add_boe_import(db_session, month=5)
    may.valor_total = Decimal("5019.8500")
    db_session.commit()

    june = service.get_monthly_summary(2026, 6)

    assert june.direct_revenue == Decimal("5019.8500")
    assert june.direct_revenue_available is True


def test_summary_reports_missing_previous_boe(service):
    summary = service.get_monthly_summary(2026, 5)
    assert summary.direct_revenue == Decimal("0.0000")
    assert summary.direct_revenue_available is False


def test_january_2026_uses_historical_direct_revenue_without_previous_boe(
    service, db_session,
):
    db_session.add(CashflowEntry(
        periodo_ano=2026, periodo_mes=1, data_lancamento=date(2026, 1, 1),
        descricao="Repasse histórico", tipo="RECEITA", origem="MANUAL",
        categoria="RECEITA_DIRETA", valor=Decimal("12870.01"), boe=False,
    ))
    db_session.commit()

    summary = service.get_monthly_summary(2026, 1)

    assert summary.direct_revenue == Decimal("12870.0100")
    assert summary.direct_revenue_available is True


def test_previous_boe_takes_priority_over_january_historical_direct(
    service, db_session,
):
    db_session.add(CashflowEntry(
        periodo_ano=2026, periodo_mes=1, data_lancamento=date(2026, 1, 1),
        descricao="Repasse histórico", tipo="RECEITA", origem="MANUAL",
        categoria="RECEITA_DIRETA", valor=Decimal("12870.01"), boe=False,
    ))
    boe = add_boe_import(db_session, year=2025, month=12)
    boe.valor_total = Decimal("13000")
    db_session.commit()

    summary = service.get_monthly_summary(2026, 1)

    assert summary.direct_revenue == Decimal("13000.0000")


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
