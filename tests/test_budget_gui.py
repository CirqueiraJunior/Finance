from decimal import Decimal

from PySide6.QtWidgets import QAbstractItemView, QDialog

from app.gui.controllers.budget_controller import BudgetController
from app.gui.pages.orcamento import BudgetDialog, OrcamentoPage
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.services.budget_service import BudgetService


def make_service(db_session):
    return BudgetService(BudgetRepository(db_session), CashflowRepository(db_session))


def test_budget_page_has_filters_cards_and_read_only_table(qtbot):
    page = OrcamentoPage()
    qtbot.addWidget(page)
    assert page.table.columnCount() == 6
    assert page.new_button.text() == "Novo Orçamento"
    assert page.month_filter.itemData(0) == 0
    assert page.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers


def test_budget_dialog_filters_categories(qtbot):
    dialog = BudgetDialog()
    qtbot.addWidget(dialog)
    assert dialog.category.count() == 2
    dialog.entry_type.setCurrentIndex(1)
    assert dialog.category.count() == 10
    assert dialog.category.findData("SOFTWARE") >= 0


def test_controller_filters_and_displays_cards(qtbot, db_session):
    service = make_service(db_session)
    service.create_budget(
        year=2026, month=7, entry_type="DESPESA", category="SOFTWARE",
        budgeted_value=Decimal("2000"),
    )
    page = OrcamentoPage()
    qtbot.addWidget(page)
    controller = BudgetController(page, service)
    page.set_period(2026, 7)
    controller.refresh()
    assert page.table.rowCount() == 1
    assert page.budgeted_expense.text() == "R$ 2.000,0000"
    assert page.actual_result.text() == "R$ 0,0000"


def test_controller_creates_budget(qtbot, db_session, monkeypatch):
    service = make_service(db_session)
    page = OrcamentoPage()
    qtbot.addWidget(page)
    controller = BudgetController(page, service)
    page.set_period(2026, 7)

    class FakeDialog:
        def __init__(self, _parent):
            self.year = StubField()
            self.month = StubField()

        def exec(self):
            return QDialog.DialogCode.Accepted

        def create_values(self):
            return 2026, 7, "DESPESA", "SOFTWARE", "2000.0000", "Teste"

    class StubField:
        def setValue(self, _value):
            pass

        def set_month(self, _value):
            pass

    monkeypatch.setattr("app.gui.controllers.budget_controller.BudgetDialog", FakeDialog)
    controller.open_new_dialog()
    assert len(service.list_by_period(2026, 7)) == 1
    assert page.table.rowCount() == 1


def test_controller_edits_budget_value_and_notes(qtbot, db_session, monkeypatch):
    service = make_service(db_session)
    budget = service.create_budget(
        year=2026, month=7, entry_type="DESPESA", category="SOFTWARE",
        budgeted_value=Decimal("2000"),
    )
    page = OrcamentoPage()
    qtbot.addWidget(page)
    page.set_period(2026, 7)
    controller = BudgetController(page, service)
    controller.refresh()
    page.table.selectRow(0)

    class FakeDialog:
        def __init__(self, _parent, _budget):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def update_values(self):
            return "2500.0000", "Revisado"

    monkeypatch.setattr("app.gui.controllers.budget_controller.BudgetDialog", FakeDialog)
    controller.open_edit_dialog()
    assert service.get_budget(budget.id).valor_orcado == Decimal("2500.0000")
    assert service.get_budget(budget.id).observacao == "Revisado"
