from datetime import date
from decimal import Decimal

import pytest

from app.core.exceptions import BudgetDuplicateError, BudgetValidationError
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.services.budget_service import BudgetService
from app.services.cashflow_service import CashflowService
from tests.boe_helpers import add_boe_import


@pytest.fixture
def service(db_session):
    return BudgetService(BudgetRepository(db_session), CashflowRepository(db_session))


def test_create_update_and_list_budget(service):
    budget = service.create_budget(
        year=2026, month=7, entry_type="DESPESA", category="SOFTWARE",
        budgeted_value=Decimal("2000.0000"), notes="Inicial",
    )
    updated = service.update_budget(
        budget.id, budgeted_value=Decimal("2500.0000"), notes="Revisado"
    )
    assert updated.valor_orcado == Decimal("2500.0000")
    assert updated.observacao == "Revisado"
    assert service.get_budget(budget.id) is updated
    assert service.list_by_period(2026, 7) == [updated]
    assert service.list_by_year(2026) == [updated]


def test_service_rejects_duplicate(service):
    values = dict(
        year=2026, month=7, entry_type="DESPESA", category="SOFTWARE",
        budgeted_value=Decimal("1"),
    )
    service.create_budget(**values)
    with pytest.raises(BudgetDuplicateError):
        service.create_budget(**values)


@pytest.mark.parametrize(
    "values",
    [
        {"year": 1999, "month": 7, "entry_type": "DESPESA", "category": "SOFTWARE"},
        {"year": 2026, "month": 13, "entry_type": "DESPESA", "category": "SOFTWARE"},
        {"year": 2026, "month": 7, "entry_type": "RECEITA", "category": "SOFTWARE"},
        {"year": 2026, "month": 7, "entry_type": "DESPESA", "category": "RECEITA_DIRETA"},
    ],
)
def test_service_rejects_invalid_budget(service, values):
    with pytest.raises(BudgetValidationError):
        service.create_budget(**values, budgeted_value=Decimal("1"))


def test_service_rejects_negative_and_float(service):
    base = dict(year=2026, month=7, entry_type="DESPESA", category="SOFTWARE")
    with pytest.raises(BudgetValidationError):
        service.create_budget(**base, budgeted_value=Decimal("-1"))
    with pytest.raises(BudgetValidationError):
        service.create_budget(**base, budgeted_value=1.5)


def test_budget_vs_actual_and_favorable_variances(service, db_session):
    cashflow = CashflowService(CashflowRepository(db_session))
    boe = add_boe_import(db_session)
    boe.valor_total = Decimal("21967.2684")
    db_session.commit()
    cashflow.create_direct_revenue_from_boe(boe)
    cashflow.create_indirect_revenue(
        year=2026, month=7, entry_date=date(2026, 7, 10),
        description="Indireta", value=Decimal("100.0000"),
    )
    cashflow.create_expense(
        year=2026, month=7, entry_date=date(2026, 7, 20),
        description="Software", category="SOFTWARE", value=Decimal("500.0000"),
    )
    service.create_budget(
        year=2026, month=7, entry_type="RECEITA", category="RECEITA_DIRETA",
        budgeted_value=Decimal("20000.0000"),
    )
    service.create_budget(
        year=2026, month=7, entry_type="RECEITA", category="RECEITA_INDIRETA",
        budgeted_value=Decimal("100.0000"),
    )
    service.create_budget(
        year=2026, month=7, entry_type="DESPESA", category="SOFTWARE",
        budgeted_value=Decimal("2000.0000"),
    )

    result = service.get_budget_vs_actual(2026, 7)
    by_category = {item.category: item for item in result.comparisons}

    assert by_category["RECEITA_DIRETA"].absolute_variance == Decimal("1967.2684")
    assert by_category["SOFTWARE"].absolute_variance == Decimal("1500.0000")
    assert by_category["SOFTWARE"].percentage_variance == Decimal("75.0000")
    assert result.summary.budgeted_revenue == Decimal("20100.0000")
    assert result.summary.actual_revenue == Decimal("22067.2684")
    assert result.summary.budgeted_expense == Decimal("2000.0000")
    assert result.summary.actual_expense == Decimal("500.0000")
    assert result.summary.budgeted_result == Decimal("18100.0000")
    assert result.summary.actual_result == Decimal("21567.2684")


def test_zero_budget_returns_null_percentage(service):
    service.create_budget(
        year=2026, month=7, entry_type="DESPESA", category="OUTROS",
        budgeted_value=Decimal("0"),
    )
    comparison = service.get_budget_vs_actual(2026, 7).comparisons[0]
    assert comparison.percentage_variance is None


def test_annual_view_sums_months(service):
    for month in (7, 8):
        service.create_budget(
            year=2026, month=month, entry_type="DESPESA", category="SOFTWARE",
            budgeted_value=Decimal("1000"),
        )
    result = service.get_budget_vs_actual(2026)
    assert result.summary.budgeted_expense == Decimal("2000.0000")
