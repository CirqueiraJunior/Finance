from datetime import date
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QLabel

from app.gui.pages.dashboard import DashboardPage
from app.gui.pages.orcamento import OrcamentoPage
from app.importers.boe_importer import BOEImporter
from app.repositories.boe_repository import BOERepository
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.investment_repository import InvestmentRepository
from app.repositories.target_repository import TargetRepository
from app.services.boe_service import BOEService
from app.services.budget_service import BudgetService, BudgetSummary, BudgetVsActual
from app.services.cashflow_service import CashflowService
from app.services.dashboard_service import DashboardService
from app.services.financial_flow_service import FinancialFlowService
from app.services.investment_service import InvestmentService
from app.services.target_service import TargetService


def _dashboard_services(db_session):
    cashflow = CashflowService(CashflowRepository(db_session))
    investments = InvestmentService(InvestmentRepository(db_session))
    boe = BOEService(
        BOERepository(db_session),
        EntityRepository(db_session),
        BOEImporter(),
        cashflow,
    )
    budget = BudgetService(
        BudgetRepository(db_session), CashflowRepository(db_session)
    )
    targets = TargetService(
        TargetRepository(db_session), EntityRepository(db_session)
    )
    dashboard = DashboardService(
        FinancialFlowService(cashflow, investments), boe, budget, targets
    )
    return dashboard, cashflow, budget


def test_dashboard_expense_comparison_respects_category(db_session):
    dashboard, _, budget = _dashboard_services(db_session)
    budget.create_budget(
        year=2026,
        month=9,
        entry_type="DESPESA",
        category="ADMINISTRATIVO",
        budgeted_value="3100",
    )

    result = dashboard.get_financial_dashboard(
        2026, 9, category="ADMINISTRATIVO"
    )["budget"]

    assert result["expense_comparison_applicable"] is True
    assert result["expense_budget_exists"] is True
    assert result["budgeted_expense"] == Decimal("3100.0000")
    assert result["actual_expense"] == Decimal("0.0000")
    assert result["expense_result"] == Decimal("3100.0000")
    assert result["expense_variation_percentage"] == Decimal("-100")


def test_dashboard_distinguishes_missing_budget_from_explicit_zero(db_session):
    dashboard, cashflow, budget = _dashboard_services(db_session)
    cashflow.create_expense(
        year=2026,
        month=10,
        entry_date=date(2026, 10, 2),
        description="Despesa sem orçamento",
        category="ADMINISTRATIVO",
        value="80",
    )

    missing = dashboard.get_financial_dashboard(
        2026, 10, category="ADMINISTRATIVO"
    )["budget"]
    assert missing["expense_budget_exists"] is False
    assert missing["expense_result"] is None
    assert missing["expense_variation_percentage"] is None

    budget.create_budget(
        year=2026,
        month=10,
        entry_type="DESPESA",
        category="ADMINISTRATIVO",
        budgeted_value="0",
    )
    explicit_zero = dashboard.get_financial_dashboard(
        2026, 10, category="ADMINISTRATIVO"
    )["budget"]
    assert explicit_zero["expense_budget_exists"] is True
    assert explicit_zero["expense_result"] == Decimal("-80.0000")
    assert explicit_zero["expense_variation_percentage"] is None


def test_dashboard_expense_comparison_rejects_incompatible_type_filter(db_session):
    dashboard, *_ = _dashboard_services(db_session)

    result = dashboard.get_financial_dashboard(
        2026, 5, category="ADMINISTRATIVO", entry_type="RECEITA"
    )["budget"]

    assert result["expense_comparison_applicable"] is False
    assert result["expense_budget_exists"] is False
    assert result["expense_result"] is None


def test_dashboard_expense_comparison_aggregates_annual_period(db_session):
    dashboard, cashflow, budget = _dashboard_services(db_session)
    for month, planned, actual in ((1, "100", "30"), (2, "200", "50")):
        budget.create_budget(
            year=2026,
            month=month,
            entry_type="DESPESA",
            category="ADMINISTRATIVO",
            budgeted_value=planned,
        )
        cashflow.create_expense(
            year=2026,
            month=month,
            entry_date=date(2026, month, 2),
            description=f"Despesa {month}",
            category="ADMINISTRATIVO",
            value=actual,
        )

    result = dashboard.get_financial_dashboard(
        2026,
        12,
        category="ADMINISTRATIVO",
        start_year=2026,
        start_month=1,
        end_year=2026,
        end_month=12,
    )["budget"]

    assert result["budgeted_expense"] == Decimal("300.0000")
    assert result["actual_expense"] == Decimal("80.0000")
    assert result["expense_result"] == Decimal("220.0000")
    assert result["expense_variation_percentage"].quantize(
        Decimal("0.01")
    ) == Decimal("-73.33")


@pytest.mark.parametrize(
    "budgeted_revenue,actual_revenue,budgeted_expense,actual_expense,expected_revenue,expected_expense",
    (
        ("200", "150", "300", "250", "50", "50"),
        ("150", "200", "250", "300", "-50", "-50"),
        ("200", "200", "300", "300", "0", "0"),
    ),
)
def test_budget_summary_results_cover_positive_negative_and_zero(
    budgeted_revenue,
    actual_revenue,
    budgeted_expense,
    actual_expense,
    expected_revenue,
    expected_expense,
):
    summary = BudgetSummary(
        Decimal(budgeted_revenue),
        Decimal(actual_revenue),
        Decimal(budgeted_expense),
        Decimal(actual_expense),
        Decimal("0"),
        Decimal("0"),
    )

    assert summary.revenue_result == Decimal(expected_revenue)
    assert summary.expense_result == Decimal(expected_expense)


def test_dashboard_budget_cards_render_missing_zero_and_keep_twelve_kpis(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    assert len(page.financial_cards) == 12
    assert len(page.budget_cards) == 4
    page._show_budget_comparison({
        "expense_comparison_applicable": True,
        "expense_budget_exists": False,
        "actual_expense": Decimal("80"),
    })
    assert page.budget_cards["budgeted"].text() == "Não orçado"
    assert page.budget_cards["actual"].text() == "R$ 80,00"
    assert page.budget_cards["result"].text() == "Não orçado"

    page._show_budget_comparison({
        "expense_comparison_applicable": True,
        "expense_budget_exists": True,
        "budgeted_expense": Decimal("0"),
        "actual_expense": Decimal("80"),
        "expense_result": Decimal("-80"),
        "expense_variation_percentage": None,
    })
    assert page.budget_cards["budgeted"].text() == "R$ 0,00"
    assert page.budget_cards["result"].text() == "R$ -80,00"
    assert page.budget_cards["variation"].text() == "N/A"

    page._show_budget_comparison({
        "expense_comparison_applicable": False,
    })
    assert all(label.text() == "N/A" for label in page.budget_cards.values())


def test_budget_page_uses_compact_result_cards(qtbot):
    page = OrcamentoPage()
    qtbot.addWidget(page)
    summary = BudgetSummary(
        Decimal("213000"),
        Decimal("200140.12"),
        Decimal("336700"),
        Decimal("247361.01"),
        Decimal("0"),
        Decimal("0"),
    )

    page.show_result(BudgetVsActual((), summary), [])

    assert page.revenue_result.text() == "R$ 12.859,88"
    assert page.expense_result.text() == "R$ 89.338,99"
    result_titles = {
        label.text()
        for label in page.findChildren(QLabel)
        if label.objectName() == "summaryLabel"
    }
    assert {"Resultado Receita", "Resultado Despesas"} <= result_titles
    margins = page.revenue_result.parentWidget().layout().contentsMargins()
    assert margins.top() == 6
    assert margins.bottom() == 6
