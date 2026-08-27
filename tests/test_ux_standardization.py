from decimal import Decimal

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from app.gui.controllers.cashflow_controller import CashflowController
from app.gui.controllers.dashboard_controller import DashboardController
from app.gui.pages.dashboard import DashboardPage
from app.gui.pages.financeiro import CashflowEntryDialog, FinanceiroPage
from app.gui.pages.metas import MetasPage, TargetDialog
from app.gui.pages.orcamento import BudgetDialog, OrcamentoPage
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.investment_repository import InvestmentRepository
from app.services.cashflow_service import CashflowService
from app.services.dashboard_service import (
    BOEDashboardSummary,
    BudgetDashboardSummary,
    DashboardSummary,
    FinancialDashboardSummary,
    IndicatorDashboardSummary,
    TargetDashboardSummary,
)
from app.services.investment_service import InvestmentService
from app.widgets import BRLCurrencyEdit, BrazilianDecimalEdit, MonthComboBox


def _empty_dashboard(year: int, month: int) -> DashboardSummary:
    zero = Decimal("0.0000")
    indicator = IndicatorDashboardSummary(False, zero, zero, None)
    return DashboardSummary(
        year,
        month,
        FinancialDashboardSummary(zero, zero, zero, zero, zero, zero, zero),
        BOEDashboardSummary(False, 0, 0, zero),
        BudgetDashboardSummary(zero, zero, zero, zero, zero, zero),
        TargetDashboardSummary(indicator, indicator),
    )


def test_month_combo_displays_names_and_preserves_numeric_values(qtbot):
    combo = MonthComboBox()
    qtbot.addWidget(combo)

    assert combo.count() == 12
    assert combo.itemText(0) == "Janeiro"
    assert combo.itemData(1) == 2
    assert combo.itemData(7) == 8
    assert combo.itemText(11) == "Dezembro"
    assert [combo.itemData(index) for index in range(12)] == list(range(1, 13))
    combo.set_month(7)
    assert combo.currentText() == "Julho"
    assert combo.month() == 7


@pytest.mark.parametrize(
    ("digits", "formatted"),
    [
        ("1", "R$ 0,01"),
        ("12", "R$ 0,12"),
        ("123", "R$ 1,23"),
        ("1234", "R$ 12,34"),
        ("123456", "R$ 1.234,56"),
        ("1234567", "R$ 12.345,67"),
    ],
)
def test_brl_currency_edit_formats_cent_typing(qtbot, digits, formatted):
    edit = BRLCurrencyEdit()
    qtbot.addWidget(edit)
    edit.show()
    edit.setFocus()

    qtbot.keyClicks(edit, digits)
    assert edit.text() == formatted


def test_brl_currency_edit_returns_decimal_and_supports_editing(qtbot):
    edit = BRLCurrencyEdit()
    qtbot.addWidget(edit)
    edit.show()
    edit.setFocus()

    qtbot.keyClicks(edit, "123456")
    assert edit.decimal_value() == Decimal("1234.56")
    qtbot.keyClick(edit, Qt.Key.Key_Backspace)
    assert edit.text() == "R$ 123,45"
    qtbot.keyClick(edit, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    qtbot.keyClick(edit, Qt.Key.Key_Delete)
    assert edit.text() == "R$ 0,00"


def test_brazilian_decimal_edit_has_no_currency_prefix(qtbot):
    edit = BrazilianDecimalEdit()
    qtbot.addWidget(edit)
    edit.show()
    edit.setFocus()

    qtbot.keyClicks(edit, "125")
    assert edit.text() == "1,25"
    assert edit.decimal_value() == Decimal("1.25")


def test_operational_pages_use_standard_month_and_value_components(qtbot):
    finance = FinanceiroPage()
    cash_dialog = CashflowEntryDialog(
        catalog_options=(), period_year=2026, period_month=8
    )
    budget = OrcamentoPage()
    budget_dialog = BudgetDialog()
    targets = MetasPage()
    target_dialog = TargetDialog([])
    for widget in (finance, cash_dialog, budget, budget_dialog, targets, target_dialog):
        qtbot.addWidget(widget)

    assert isinstance(finance.month_filter, MonthComboBox)
    assert isinstance(cash_dialog.month_input, MonthComboBox)
    assert isinstance(cash_dialog.value, BRLCurrencyEdit)
    assert cash_dialog.month_input.month() == 8
    assert isinstance(budget.month_filter, MonthComboBox)
    assert isinstance(budget_dialog.month, MonthComboBox)
    assert isinstance(budget_dialog.budgeted_value, BRLCurrencyEdit)
    assert isinstance(targets.month_filter, MonthComboBox)
    assert isinstance(target_dialog.month, MonthComboBox)
    assert isinstance(target_dialog.target_value, BrazilianDecimalEdit)
    assert isinstance(target_dialog.actual_value, BrazilianDecimalEdit)


def test_dashboard_refresh_button_responds_to_real_mouse_click(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    class ServiceStub:
        def __init__(self):
            self.calls = 0

        def get_dashboard_summary(self, year, month):
            self.calls += 1
            return _empty_dashboard(year, month)

    service = ServiceStub()
    controller = DashboardController(page, service)
    calls_after_initial_load = service.calls
    page.show()

    qtbot.mouseClick(page.refresh_button, Qt.MouseButton.LeftButton)

    assert service.calls == calls_after_initial_load + 1
    assert controller.view.status.text().startswith("Dashboard atualizado")


def test_cashflow_new_entry_button_opens_dialog_on_real_mouse_click(
    qtbot, db_session, monkeypatch
):
    page = FinanceiroPage()
    qtbot.addWidget(page)
    opened = []

    class TrackingDialog(CashflowEntryDialog):
        def __init__(self, *args, **kwargs):
            opened.append((kwargs["period_year"], kwargs["period_month"]))
            super().__init__(*args, **kwargs)

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(
        "app.gui.controllers.cashflow_controller.CashflowEntryDialog",
        TrackingDialog,
    )
    controller = CashflowController(
        page,
        CashflowService(CashflowRepository(db_session)),
        InvestmentService(InvestmentRepository(db_session)),
    )
    page.set_period(2026, 7)
    page.show()

    qtbot.mouseClick(page.new_entry_button, Qt.MouseButton.LeftButton)

    assert opened == [(2026, 7)]
    assert controller.view is page
