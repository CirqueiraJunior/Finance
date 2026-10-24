from datetime import date
from decimal import Decimal
import threading

from PySide6.QtWidgets import QAbstractItemView, QLabel, QSizePolicy

from app.gui.controllers.cashflow_controller import CashflowController
from app.gui.pages.financeiro import CashflowEntryDialog, FinanceiroPage
from app.gui.processing import ProcessingDialog
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.investment_repository import InvestmentRepository
from app.services.cashflow_service import CashflowService
from app.services.investment_service import InvestmentService
from tests.cashflow_helpers import make_manual_entry
from tests.boe_helpers import add_boe_import
from app.widgets.sidebar import Sidebar


def make_controller(page, db_session):
    return CashflowController(
        page, CashflowService(CashflowRepository(db_session)),
        InvestmentService(InvestmentRepository(db_session)),
    )


def test_cashflow_page_contains_unified_table_and_seven_cards(qtbot):
    page = FinanceiroPage()
    qtbot.addWidget(page)
    assert page.entries_table.columnCount() == 7
    assert page.new_entry_button.text() == "Novo Lançamento"
    assert page.entries_table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert page.applications_total.text() == "R$ 0,00"
    assert not hasattr(page, "cash_movement")
    assert ("Aplicações e Resgates", "investimentos") not in Sidebar.ITEMS


def test_financeiro_layout_orders_filters_kpis_table_and_import(qtbot):
    page = FinanceiroPage()
    qtbot.addWidget(page)
    assert page.scroll_area.widgetResizable()
    assert page.scroll_area.widget() is not None
    assert page.layout().indexOf(page.scroll_area) >= 0
    layout = page.scroll_area.widget().layout()

    def layout_index(target):
        return next(
            index for index in range(layout.count())
            if layout.itemAt(index).layout() is target
        )

    filters = layout.itemAt(2).layout()
    cards = layout.itemAt(3).layout()
    kpi_titles = [
        item.widget().findChild(QLabel, "summaryLabel").text()
        for item in (cards.itemAt(index) for index in range(cards.count()))
        if item.widget() is not None
    ]
    assert kpi_titles == [
        "Saldo Inicial", "Receita Direta", "Receita Indireta", "Receita Total",
        "Despesa Total", "Saldo do Período", "Aplicações", "Resgates",
        "Receita Líquida", "Valor BOE", "Saldo Bancário", "Saldo Aplicado",
    ]
    assert cards.rowCount() == 3
    assert cards.columnCount() == 4

    assert layout_index(filters) < layout_index(cards)
    assert layout_index(cards) < layout.indexOf(page.entries_table)
    assert layout.indexOf(page.entries_table) < layout.indexOf(page.import_box)
    import_layout = page.import_box.layout()
    assert import_layout.indexOf(page.import_panel) >= 0
    panel_layout = page.import_panel.layout()
    assert panel_layout.indexOf(page.import_steps) >= 0
    assert panel_layout.indexOf(page.selected_import_file) >= 0
    assert panel_layout.indexOf(page.import_preview) >= 0
    assert panel_layout.indexOf(page.operation_status) >= 0
    assert (
        panel_layout.indexOf(page.import_preview)
        < panel_layout.indexOf(page.operation_status)
    )
    assert page.import_issues.isReadOnly()
    assert page.import_result.isReadOnly()
    assert page.import_issues.parentWidget() is not None
    assert page.import_result.parentWidget() is not None
    assert page.entries_table.minimumHeight() == 92
    assert page.entries_table.maximumHeight() <= 125
    assert page.entries_table.sizePolicy().verticalPolicy() == (
        QSizePolicy.Policy.Preferred
    )
    page.set_available_years([2026])
    page.set_period(2026, 1)
    assert page.selected_period() == (2026, 1)
    assert page.new_entry_button.text() == "Novo Lançamento"


def test_new_entry_dialog_offers_four_types_and_context_fields(qtbot):
    dialog = CashflowEntryDialog()
    qtbot.addWidget(dialog)
    assert [dialog.entry_type.itemData(i) for i in range(4)] == [
        "RECEITA", "DESPESA", "APLICACAO", "RESGATE"
    ]
    assert dialog.category.count() == 1
    dialog.entry_type.setCurrentIndex(1)
    assert {
        dialog.category.itemData(i)
        for i in range(dialog.category.count())
    } == {
        "ADMINISTRATIVO",
        "DIRETORIA",
        "EVENTOS",
        "OPERACIONAL",
        "PESSOAL",
        "INVESTIMENTO",
        "OUTROS",
    }
    dialog.entry_type.setCurrentIndex(2)
    assert not dialog.category.isVisible()
    dialog.show()
    dialog.entry_type.setCurrentIndex(3)
    assert dialog.available_balance.isVisible()


def test_filters_show_cashflow_and_investments_together(qtbot, db_session):
    cash_repository = CashflowRepository(db_session)
    cash_repository.add(make_manual_entry())
    cash_repository.add(make_manual_entry(month=8))
    db_session.commit()
    investments = InvestmentService(InvestmentRepository(db_session))
    investments.create_application(
        movement_date=date(2026, 7, 5), description="Aplicação", value="10000"
    )
    investments.create_redemption(
        movement_date=date(2026, 7, 20), description="Resgate", value="2500"
    )
    page = FinanceiroPage()
    qtbot.addWidget(page)
    page.set_period(2026, 7)
    controller = CashflowController(
        page, CashflowService(cash_repository), investments
    )
    controller.refresh_entries()
    assert page.entries_table.rowCount() == 3
    assert {page.entries_table.item(row, 1).text() for row in range(3)} == {
        "RECEITA", "APLICACAO", "RESGATE"
    }
    investment_rows = [
        row for row in range(3)
        if page.entries_table.item(row, 1).text() in {"APLICACAO", "RESGATE"}
    ]
    assert {
        page.entries_table.item(row, 3).text() for row in investment_rows
    } == {"Investimento", "Resgate"}
    assert all(page.entries_table.item(row, 5).text() == "Não" for row in investment_rows)


def test_homologation_cards_use_correct_semantics(qtbot, db_session):
    cashflow = CashflowService(CashflowRepository(db_session))
    boe = add_boe_import(db_session, month=6)
    boe.valor_total = Decimal("21967.2684")
    db_session.commit()
    cashflow.create_direct_revenue_from_boe(boe)
    cashflow.create_indirect_revenue(
        year=2026, month=7, entry_date=date(2026, 7, 10),
        description="Indireta", value="100.0000",
    )
    cashflow.create_expense(
        year=2026, month=7, entry_date=date(2026, 7, 15),
        description="Software", category="ADMINISTRATIVO", value="500.0000",
    )
    investments = InvestmentService(InvestmentRepository(db_session))
    investments.create_application(
        movement_date=date(2026, 7, 5), description="Aplicação", value="10000"
    )
    investments.create_redemption(
        movement_date=date(2026, 7, 20), description="Resgate", value="2500"
    )
    page = FinanceiroPage()
    qtbot.addWidget(page)
    page.set_period(2026, 7)
    controller = CashflowController(page, cashflow, investments)
    controller.refresh_entries()
    assert page.revenue_total.text() == "R$ 22.067,27"
    assert page.expense_total.text() == "R$ 500,00"
    assert page.applications_total.text() == "R$ 10.000,00"
    assert page.redemptions_total.text() == "R$ 2.500,00"
    assert page.operational_result.text() == "R$ 21.567,27"
    assert page.period_balance.text() == "R$ 21.567,27"
    assert page.direct_total.text() == "R$ 21.967,27"
    assert page.indirect_total.text() == "R$ 100,00"
    assert page.operational_result.parentWidget().findChild(
        QLabel, "summaryLabel"
    ).text() == "Saldo do Período"
    assert not hasattr(page, "cash_movement")
    assert page.applied_balance.text() == "R$ 7.500,00"


class _FinancialImportRemote:
    def __init__(self):
        self.release = threading.Event()
        self.calls = 0
        self.validation_paths = []

    def validate_import(self, path):
        self.validation_paths.append(path)
        return {
            "preview": [{
                "line": 3, "year": 2026, "month": 4,
                "type": "DESPESA", "description": "Energia",
                "category": "ADMINISTRATIVO", "boe": False, "value": "40",
            }],
            "warnings": ["Aviso não bloqueante"], "errors": [],
            "can_import": True,
        }

    def import_file(self, _path):
        self.calls += 1
        self.release.wait(2)
        return {"imported": 1, "ignored": 0, "warnings": []}


def test_financial_workflow_enables_validate_only_after_file_selection(
    qtbot, db_session, monkeypatch,
):
    page = FinanceiroPage()
    qtbot.addWidget(page)
    remote = _FinancialImportRemote()
    controller = CashflowController(
        page,
        CashflowService(CashflowRepository(db_session)),
        InvestmentService(InvestmentRepository(db_session)),
        import_service=remote,
        defer_initial_load=True,
    )

    monkeypatch.setattr(
        "app.gui.controllers.cashflow_controller.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: ("", ""),
    )
    assert [button.isEnabled() for button in page.import_steps.buttons] == [
        True, False, False, False,
    ]
    page.import_steps.buttons[0].click()
    assert controller.import_file_path is None
    assert [button.isEnabled() for button in page.import_steps.buttons] == [
        True, False, False, False,
    ]

    monkeypatch.setattr(
        "app.gui.controllers.cashflow_controller.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: ("financeiro.xlsx", ""),
    )
    page.import_steps.buttons[0].click()
    assert [button.isEnabled() for button in page.import_steps.buttons] == [
        True, True, False, False,
    ]
    page.import_steps.buttons[1].click()
    assert remote.validation_paths == ["financeiro.xlsx"]
    assert [button.isEnabled() for button in page.import_steps.buttons] == [
        True, True, True, False,
    ]

    for stage in range(3, 5):
        page.import_steps.set_stage_enabled(stage, True)
    monkeypatch.setattr(
        "app.gui.controllers.cashflow_controller.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: ("outro_financeiro.xlsx", ""),
    )
    page.import_steps.buttons[0].click()
    assert controller.import_file_path == "outro_financeiro.xlsx"
    assert [button.isEnabled() for button in page.import_steps.buttons] == [
        True, True, False, False,
    ]
    assert controller._last_import_validation is None


def test_financial_workflow_compares_validation_without_importing(
    qtbot, db_session, monkeypatch,
):
    from PySide6.QtWidgets import QMessageBox

    page = FinanceiroPage()
    qtbot.addWidget(page)

    class BlockedRemote:
        def __init__(self):
            self.validations = 0
            self.imports = 0

        def validate_import(self, _path):
            self.validations += 1
            if self.validations > 1:
                raise RuntimeError("Falha sintética de revalidação")
            return {
                "file_name": "inconsistente.xlsx",
                "preview": [
                    {
                        "line": 3, "year": 2026, "month": 4,
                        "type": "DESPESA", "description": "Energia",
                        "category": "ADMINISTRATIVO", "boe": False,
                        "value": "40", "duplicate": True,
                    },
                    {
                        "line": 4, "year": 2026, "month": 4,
                        "type": "DESPESA", "description": "Água",
                        "category": "ADMINISTRATIVO", "boe": False,
                        "value": "20",
                    },
                ],
                "warnings": ["Aviso detalhado mantido no painel"],
                "errors": ["Erro detalhado mantido no painel"],
                "duplicates": 1,
                "can_import": False,
            }

        def import_file(self, _path):
            self.imports += 1
            raise AssertionError("Comparar não pode executar importação")

    remote = BlockedRemote()
    controller = CashflowController(
        page,
        CashflowService(CashflowRepository(db_session)),
        InvestmentService(InvestmentRepository(db_session)),
        import_service=remote,
        defer_initial_load=True,
    )
    monkeypatch.setattr(
        "app.gui.controllers.cashflow_controller.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: ("inconsistente.xlsx", ""),
    )
    captured = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda *args: captured.append(args[2]),
    )

    page.import_steps.buttons[0].click()
    page.import_steps.buttons[1].click()
    assert [button.isEnabled() for button in page.import_steps.buttons] == [
        True, True, True, False,
    ]

    page.import_steps.buttons[2].click()
    assert captured == []
    assert controller._authorized_import_file is None
    assert not page.import_steps.buttons[3].isEnabled()
    assert "Aviso detalhado mantido no painel" in (
        page.import_issues.toPlainText()
    )
    assert "Erro detalhado mantido no painel" in (
        page.import_issues.toPlainText()
    )
    assert remote.imports == 0

    page.import_steps.buttons[1].click()
    assert controller._last_import_validation is None
    assert [button.isEnabled() for button in page.import_steps.buttons] == [
        True, True, False, False,
    ]


def test_financial_preview_and_reused_modal_block_duplicate_import(qtbot, db_session, monkeypatch):
    page = FinanceiroPage()
    qtbot.addWidget(page)
    remote = _FinancialImportRemote()
    controller = CashflowController(
        page, CashflowService(CashflowRepository(db_session)),
        InvestmentService(InvestmentRepository(db_session)), import_service=remote,
    )
    refreshes = []
    controller.import_completed.connect(lambda: refreshes.append(True))
    controller.import_file_path = "financeiro.xlsx"
    # Simulate explicit user acceptance of the final dialog.
    # Preserve the original asynchronous duplicate-import assertions.
    monkeypatch.setattr(
        controller,
        "_request_final_import_confirmation",
        lambda: True,
    )

    page.import_steps.buttons[1].setEnabled(True)

    controller.validate_import_file()
    assert not page.import_steps.buttons[3].isEnabled()
    assert page.import_preview.rowCount() == 1
    assert "Aviso não bloqueante" in page.import_issues.toPlainText()

    controller.import_validated_file()
    qtbot.waitUntil(lambda: remote.calls == 1)
    assert isinstance(controller._import_dialog, ProcessingDialog)
    assert controller._import_dialog.isVisible()
    controller.import_validated_file()
    assert remote.calls == 1

    remote.release.set()
    qtbot.waitUntil(lambda: controller._import_thread is None)
    assert controller._import_dialog is None
    assert page.import_steps.buttons[0].isEnabled()
    assert "concluída" in page.operation_status.text()
    assert refreshes == [True]


def test_financial_import_refreshes_years_and_uses_real_line_breaks(
    qtbot, db_session, monkeypatch,
):
    page = FinanceiroPage()
    qtbot.addWidget(page)
    cashflow = CashflowService(CashflowRepository(db_session))
    controller = CashflowController(
        page,
        cashflow,
        InvestmentService(InvestmentRepository(db_session)),
        import_service=_FinancialImportRemote(),
        defer_initial_load=True,
    )
    page.year_filter.clear()
    controller._last_import_validation = {
        "preview": [{"year": 2026, "month": 1}],
        "can_import": True,
    }
    monkeypatch.setattr(controller._years_loader, "operation", lambda: [2026])

    controller._import_succeeded({
        "imported": 18,
        "ignored": 1,
        "warnings": [],
    })

    assert page.year_filter.currentData() == 2026
    text = page.import_result.toPlainText()
    assert text.splitlines() == [
        "Importação concluída com sucesso.",
        "Importados: 18",
        "Ignorados: 1",
        "Avisos: 0.",
    ]
    assert r"\n" not in text
