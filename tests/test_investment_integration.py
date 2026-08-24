from datetime import date
from decimal import Decimal

from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.investment_repository import InvestmentRepository
from app.services.cashflow_service import CashflowService
from app.services.investment_service import InvestmentService
from tests.boe_helpers import add_boe_import


def test_investment_movements_do_not_change_cashflow_totals(db_session):
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
    before = cashflow.get_monthly_summary(2026, 7)
    investments = InvestmentService(InvestmentRepository(db_session))
    investments.create_application(
        movement_date=date(2026, 7, 5), description="Aplicação", value="10000"
    )
    investments.create_redemption(
        movement_date=date(2026, 7, 20), description="Resgate", value="2500"
    )
    assert cashflow.get_monthly_summary(2026, 7) == before
