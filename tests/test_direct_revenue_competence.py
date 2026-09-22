from decimal import Decimal

from app.importers.boe_importer import BOEImporter
from app.repositories.boe_repository import BOERepository
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.investment_repository import InvestmentRepository
from app.services.boe_service import BOEService
from app.services.budget_service import BudgetService
from app.services.cashflow_service import CashflowService
from app.services.financial_flow_service import FinancialFlowService
from app.services.investment_service import InvestmentService
from app.services.report_service import ReportService
from tests.boe_helpers import add_boe_import


def test_reports_and_financial_flow_share_previous_boe_rule(db_session):
    cashflow_repository = CashflowRepository(db_session)
    cashflow = CashflowService(cashflow_repository)
    april = add_boe_import(db_session, month=4, file_hash="4" * 64)
    april.valor_total = Decimal("4857.9200")
    may = add_boe_import(db_session, month=5, file_hash="5" * 64)
    may.valor_total = Decimal("5019.8500")
    db_session.commit()
    flow = FinancialFlowService(
        cashflow, InvestmentService(InvestmentRepository(db_session))
    )
    boe = BOEService(
        BOERepository(db_session), EntityRepository(db_session), BOEImporter(), cashflow
    )
    budget = BudgetService(BudgetRepository(db_session), cashflow_repository)
    report = ReportService(flow, boe, budget).get_annual_report(2026)

    assert flow.get_summary(2026, 5).direct_revenue == Decimal("4857.9200")
    assert report.rows[4].total_revenue == Decimal("4857.9200")
    assert report.rows[5].total_revenue == Decimal("5019.8500")
