from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import QAbstractItemView, QDialog

from app.gui.controllers.cashflow_controller import CashflowController
from app.gui.pages.financeiro import CashflowEntryDialog, FinanceiroPage
from app.repositories.cashflow_repository import CashflowRepository
from app.services.cashflow_service import CashflowService
from tests.cashflow_helpers import make_manual_entry


def test_cashflow_page_opens_with_required_components(qtbot):
    page = FinanceiroPage()
    qtbot.addWidget(page)

    assert page.entries_table.columnCount() == 6
    assert page.new_entry_button.text() == "Novo Lançamento"
    assert page.entries_table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers


def test_cashflow_page_calculates_summary_and_shows_direct_as_read_only(qtbot):
    page = FinanceiroPage()
    qtbot.addWidget(page)
    direct = make_manual_entry()
    direct.origem = "BOE"
    direct.categoria = "RECEITA_DIRETA"
    direct.valor = Decimal("21967.2684")
    indirect = make_manual_entry()
    indirect.valor = Decimal("100.0000")

    page.show_entries([direct, indirect])

    assert page.direct_total.text() == "R$ 21.967,2684"
    assert page.indirect_total.text() == "R$ 100,0000"
    assert page.revenue_total.text() == "R$ 22.067,2684"
    assert page.entries_table.item(0, 4).text() == "BOE"


def test_controller_filter_loads_selected_period(qtbot, db_session):
    repository = CashflowRepository(db_session)
    repository.add(make_manual_entry())
    repository.add(make_manual_entry(month=8))
    db_session.commit()
    page = FinanceiroPage()
    qtbot.addWidget(page)
    controller = CashflowController(page, CashflowService(repository))

    page.set_period(2026, 7)
    controller.refresh_entries()

    assert page.entries_table.rowCount() == 1


def test_controller_creates_indirect_revenue(qtbot, db_session, monkeypatch):
    page = FinanceiroPage()
    qtbot.addWidget(page)
    page.set_period(2026, 7)
    service = CashflowService(CashflowRepository(db_session))
    controller = CashflowController(page, service)

    class FakeDialog:
        def __init__(self, _parent):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def values(self):
            return (
                "RECEITA", date(2026, 7, 20), "Receita GUI",
                "RECEITA_INDIRETA", "50.2500", "Teste",
            )

    monkeypatch.setattr(
        "app.gui.controllers.cashflow_controller.CashflowEntryDialog", FakeDialog
    )
    controller.open_indirect_revenue_dialog()

    assert page.entries_table.rowCount() == 1
    assert service.list_entries()[0].boe_import_id is None


def test_new_entry_dialog_filters_categories_by_type(qtbot):
    dialog = CashflowEntryDialog()
    qtbot.addWidget(dialog)

    assert dialog.category.count() == 1
    assert dialog.category.currentData() == "RECEITA_INDIRETA"
    dialog.entry_type.setCurrentIndex(1)
    assert dialog.category.count() == 10
    assert "SOFTWARE" in [dialog.category.itemData(i) for i in range(10)]


def test_controller_creates_expense(qtbot, db_session, monkeypatch):
    page = FinanceiroPage()
    qtbot.addWidget(page)
    page.set_period(2026, 7)
    service = CashflowService(CashflowRepository(db_session))
    controller = CashflowController(page, service)

    class FakeDialog:
        def __init__(self, _parent):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def values(self):
            return (
                "DESPESA", date(2026, 7, 20), "Despesa GUI",
                "SOFTWARE", "500.0000", "Teste",
            )

    monkeypatch.setattr(
        "app.gui.controllers.cashflow_controller.CashflowEntryDialog", FakeDialog
    )
    controller.open_new_entry_dialog()

    entry = service.list_entries()[0]
    assert entry.tipo == "DESPESA"
    assert page.expense_total.text() == "R$ 500,0000"
    assert page.monthly_balance.text() == "R$ -500,0000"
