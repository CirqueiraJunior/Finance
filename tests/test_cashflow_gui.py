from datetime import date
from decimal import Decimal

from PySide6.QtWidgets import QAbstractItemView, QDialog

from app.gui.controllers.cashflow_controller import CashflowController
from app.gui.pages.financeiro import FinanceiroPage
from app.repositories.cashflow_repository import CashflowRepository
from app.services.cashflow_service import CashflowService
from tests.cashflow_helpers import make_manual_entry


def test_cashflow_page_opens_with_required_components(qtbot):
    page = FinanceiroPage()
    qtbot.addWidget(page)

    assert page.entries_table.columnCount() == 5
    assert page.new_indirect_button.text() == "Nova Receita Indireta"
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
    assert page.entries_table.item(0, 3).text() == "BOE"


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
            return date(2026, 7, 20), "Receita GUI", "50.2500", "Teste"

    monkeypatch.setattr(
        "app.gui.controllers.cashflow_controller.IndirectRevenueDialog", FakeDialog
    )
    controller.open_indirect_revenue_dialog()

    assert page.entries_table.rowCount() == 1
    assert service.list_entries()[0].boe_import_id is None
