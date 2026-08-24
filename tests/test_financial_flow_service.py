from datetime import date
from decimal import Decimal

from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.investment_repository import InvestmentRepository
from app.services.cashflow_service import CashflowService
from app.services.financial_flow_service import FinancialFlowService
from app.services.investment_service import InvestmentService
from tests.cashflow_helpers import make_manual_entry
from tests.boe_helpers import add_boe_import


def test_unified_flow_keeps_types_and_calculates_cash_movement(db_session):
    cashflow = CashflowService(CashflowRepository(db_session))
    boe = add_boe_import(db_session)
    boe.valor_total = Decimal("21967.2684")
    db_session.commit()
    cashflow.create_direct_revenue_from_boe(boe)
    cashflow.create_indirect_revenue(
        year=2026, month=7, entry_date=date(2026, 7, 10),
        description="Indireta", value="100.0000",
    )
    cashflow.create_expense(
        year=2026, month=7, entry_date=date(2026, 7, 15),
        description="Software", category="SOFTWARE", value="500.0000",
    )
    investments = InvestmentService(InvestmentRepository(db_session))
    investments.create_application(
        movement_date=date(2026, 7, 5), description="Aplicação", value="10000"
    )
    investments.create_redemption(
        movement_date=date(2026, 7, 20), description="Resgate", value="2500"
    )
    flow = FinancialFlowService(cashflow, investments)
    summary = flow.get_summary(2026, 7)
    assert summary.operational_result == Decimal("21567.2684")
    assert summary.cash_movement == Decimal("14067.2684")
    assert summary.applied_balance == Decimal("7500.0000")
    assert {item.movement_type for item in flow.list_by_period(2026, 7)} == {
        "RECEITA", "DESPESA", "APLICACAO", "RESGATE"
    }
