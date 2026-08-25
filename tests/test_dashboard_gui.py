from decimal import Decimal

from PySide6.QtCharts import QChartView

from app.gui.controllers.dashboard_controller import DashboardController
from app.gui.pages.dashboard import DashboardPage
from app.services.dashboard_service import (
    BOEDashboardSummary,
    BudgetDashboardSummary,
    DashboardSummary,
    FinancialDashboardSummary,
    IndicatorDashboardSummary,
    TargetDashboardSummary,
)


ZERO = Decimal("0.0000")


def summary(*, has_data=True, revenue=Decimal("22067.2684")):
    return DashboardSummary(
        2026,
        7,
        FinancialDashboardSummary(
            revenue, Decimal("500.0000"), Decimal("21567.2684"),
            Decimal("10000.0000"), Decimal("2500.0000"),
            Decimal("14067.2684"), Decimal("7500.0000"),
        ),
        BOEDashboardSummary(has_data, 77 if has_data else 0, 316988 if has_data else 0, Decimal("21967.2684") if has_data else ZERO),
        BudgetDashboardSummary(
            Decimal("20200.0000"), revenue, Decimal("2000.0000"),
            Decimal("500.0000"), Decimal("18200.0000"), Decimal("21567.2684"),
        ),
        TargetDashboardSummary(
            IndicatorDashboardSummary(has_data, Decimal("1271634.8800") if has_data else ZERO, Decimal("1153124.2400") if has_data else ZERO, Decimal("90.6805") if has_data else None),
            IndicatorDashboardSummary(has_data, Decimal("166763.9400") if has_data else ZERO, Decimal("173762.6500") if has_data else ZERO, Decimal("104.1968") if has_data else None),
        ),
    )


def test_dashboard_page_has_filters_cards_and_three_charts(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    assert page.selected_period()[1] in range(1, 13)
    assert len(page.financial_cards) == 7
    assert page.budget_table.rowCount() == 3
    assert len(page.findChildren(QChartView)) == 3


def test_dashboard_page_displays_complete_summary(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    page.show_summary(summary())

    assert page.financial_cards["total_revenue"].text() == "R$ 22.067,2684"
    assert page.boe_entities.text() == "77"
    assert page.boe_queries.text() == "316.988"
    assert page.budget_table.item(0, 1).text() == "R$ 20.200,0000"
    assert page.query_achievement.text() == "90,6805%"
    assert page.registration_achievement.text() == "104,1968%"
    assert not page.boe_state.isVisible()
    assert not page.target_state.isVisible()
    assert page.finance_chart.chart().title() == "Receitas x Despesas"
    assert page.budget_chart.chart().title() == "Orçado x Realizado"
    assert page.target_chart.chart().title() == "Atingimento das Metas"


def test_dashboard_page_displays_partial_absence_without_crash(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    page.show_summary(summary(has_data=False, revenue=ZERO))

    assert page.boe_entities.text() == "0"
    assert page.boe_state.text() == "Sem dados BOE para o período."
    assert page.target_state.text() == "Sem dados de Meta x Realizado para o período."
    assert page.query_achievement.text() == "—"


def test_controller_updates_all_blocks_when_filter_changes(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    class ServiceStub:
        def __init__(self):
            self.calls = []

        def get_dashboard_summary(self, year, month):
            self.calls.append((year, month))
            return summary(revenue=Decimal("100.0000") if month == 8 else Decimal("22067.2684"))

    service = ServiceStub()
    controller = DashboardController(page, service)
    page.set_period(2026, 8)
    controller.refresh()

    assert service.calls[-1] == (2026, 8)
    assert page.financial_cards["total_revenue"].text() == "R$ 100,0000"
    assert "08/2026" in page.status.text()
