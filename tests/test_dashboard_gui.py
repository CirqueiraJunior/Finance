from decimal import Decimal

from PySide6.QtCharts import QChartView

from app.gui.controllers.dashboard_controller import DashboardController
from app.gui.pages.dashboard import DashboardChartView, DashboardPage
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


def test_dashboard_page_has_area_filters_complete_cards_and_charts(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    assert page.selected_period()[1] in range(1, 13)
    assert len(page.financial_cards) == 10
    assert page.budget_table.rowCount() == 3
    assert len(page.findChildren(QChartView)) == 14
    assert [page.tabs.tabText(index) for index in range(page.tabs.count())] == [
        "Financeiro", "BOE", "Meta x Realizado"
    ]


def test_dashboard_hides_unauthorized_internal_areas(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    page.set_allowed_areas({"boe"})

    assert page.tabs.isTabVisible(page.tabs.indexOf(page._tab_pages["boe"]))
    assert not page.tabs.isTabVisible(page.tabs.indexOf(page._tab_pages["financial"]))
    assert not page.tabs.isTabVisible(page.tabs.indexOf(page._tab_pages["targets"]))


def test_dashboard_page_displays_complete_summary(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    page.show_summary(summary())

    assert page.financial_cards["total_revenue"].text() == "R$ 22.067,27"
    assert page.boe_entities.text() == "77"
    assert page.boe_queries.text() == "316.988"
    assert page.budget_table.item(0, 1).text() == "R$ 20.200,00"
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
    assert page.financial_cards["total_revenue"].text() == "R$ 100,00"
    assert "08/2026" in page.status.text()


def test_dashboard_month_selector_and_distribution_percentages(qtbot):
    page=DashboardPage(); qtbot.addWidget(page)
    assert page.month_filter.objectName() == "dashboardMonthFilter"
    assert page.month_filter.minimumWidth() >= 120
    chart=page._distribution_chart("Distribuição", {"A": Decimal("25"), "B": Decimal("75")}, "Receita")
    axis=next(axis for axis in chart.axes() if hasattr(axis, "categories"))
    assert axis.categories() == ["A (25,0%)", "B (75,0%)"]


def test_dense_dashboard_chart_keeps_compact_bar_labels(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)
    chart = page._bar_chart("Mensal", [str(m) for m in range(1, 13)], [("Receita", [100] * 12), ("Despesa", [80] * 12)])
    assert chart.series()[0].isLabelsVisible() is False
    assert "Receita" in chart.series()[0].barSets()[0].label()


def test_short_dashboard_chart_keeps_value_labels(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)
    chart = page._bar_chart("Curto", ["A", "B"], [("Valor", [10, 20])])
    assert chart.series()[0].isLabelsVisible() is False



def test_dashboard_chart_overlay_formats_readable_values(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)
    assert DashboardChartView._format_chart_value(44502, "number") == "44,5 mil"
    assert DashboardChartView._format_chart_value(1441296, "number") == "1,4 mi"
    assert DashboardChartView._format_chart_value(99.1366, "percentage") == "99,1%"
    chart = page._bar_chart("% Atingimento", ["1", "2"], [("Atingimento %", [99.1, 104.2])])
    assert chart.series()[0].isLabelsVisible() is False
    assert chart.series()[0].barSets()[0].label() == "Atingimento %"


def test_budget_monthly_chart_uses_absolute_result_for_visual_comparison(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)
    budgeted = abs(page.decimal("10000") - page.decimal("25000"))
    actual = abs(page.decimal("12000") - page.decimal("20000"))
    chart = page._bar_chart("Orçado x Realizado mensal", ["1"], [("Orçado", [budgeted]), ("Realizado", [actual])])
    values = chart._dashboard_labels["series_values"]
    assert values == [[15000.0], [8000.0]]
    assert all(value >= 0 for series in values for value in series)


def test_dashboard_month_labels_use_portuguese_abbreviations(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)
    assert [page.month_label(month) for month in range(1, 13)] == [
        "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
        "Jul", "Ago", "Set", "Out", "Nov", "Dez",
    ]


def test_dashboard_bar_charts_show_values_and_year_has_no_arrows(qtbot):
    from PySide6.QtWidgets import QAbstractSpinBox

    page = DashboardPage()
    qtbot.addWidget(page)

    assert page.year_filter.buttonSymbols() == QAbstractSpinBox.ButtonSymbols.NoButtons

    chart = page._bar_chart(
        "Teste", ["Jan", "Fev"], [("Receita", [10, 20])]
    )
    series = chart.series()[0]
    assert series.isLabelsVisible() is False
    assert series.barSets()[0].label() == "Receita"
