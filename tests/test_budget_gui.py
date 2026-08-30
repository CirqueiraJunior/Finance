from decimal import Decimal

from PySide6.QtWidgets import QAbstractItemView, QDialog

from app.gui.controllers.budget_controller import BudgetController
from app.gui.pages.orcamento import BudgetDialog, OrcamentoPage
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.cashflow_catalog_repository import CashflowCatalogRepository
from app.services.budget_service import BudgetService
from app.services.cashflow_catalog_service import CashflowCatalogOption, CashflowCatalogService


def make_service(db_session):
    return BudgetService(BudgetRepository(db_session), CashflowRepository(db_session))


def test_budget_page_has_filters_cards_and_read_only_table(qtbot):
    page = OrcamentoPage()
    qtbot.addWidget(page)
    assert page.table.columnCount() == 8
    assert page.table.horizontalHeaderItem(7).text() == "Observação"
    assert page.table.horizontalHeaderItem(1).text() == "Descrição"
    assert page.new_button.text() == "Novo Orçamento"
    assert page.month_filter.itemData(0) == 0
    assert page.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers


def test_budget_dialog_filters_categories(qtbot):
    options = (
        CashflowCatalogOption("Mensalidade", "RECEITA_INDIRETA", "RECEITA"),
        CashflowCatalogOption("Serviços", "RECEITA_INDIRETA", "RECEITA"),
        CashflowCatalogOption("Licença", "ADMINISTRATIVO", "DESPESA"),
        CashflowCatalogOption("Licença", "OUTROS", "DESPESA"),
    )
    dialog = BudgetDialog(catalog_options=options)
    qtbot.addWidget(dialog)
    assert dialog.description.count() == 4
    assert dialog.category.currentData() is None
    dialog.description.setCurrentIndex(dialog.description.findData("Licença"))
    assert dialog.category.count() == 3
    assert dialog.category.findData("ADMINISTRATIVO") >= 0
    dialog.category.setCurrentIndex(dialog.category.findData("ADMINISTRATIVO"))
    assert dialog.entry_type.currentData() == "DESPESA"
    assert dialog.entry_type.isEnabled() is False


def test_budget_dialog_excludes_non_budget_movements(qtbot):
    dialog = BudgetDialog(catalog_options=(
        CashflowCatalogOption("Aplicação", "INVESTIMENTO", "APLICACAO"),
        CashflowCatalogOption("Resgate", "RESGATE", "RESGATE"),
        CashflowCatalogOption("Saldo", "SALDO_APLICADO", "SALDO"),
        CashflowCatalogOption("Despesa", "ADMINISTRATIVO", "DESPESA"),
    ))
    qtbot.addWidget(dialog)
    assert dialog.description.findData("Aplicação") == -1
    assert dialog.description.findData("Resgate") == -1
    assert dialog.description.findData("Saldo") == -1
    assert dialog.description.findData("Despesa") >= 0


def test_controller_filters_and_displays_cards(qtbot, db_session):
    service = make_service(db_session)
    service.create_budget(
        year=2026, month=7, entry_type="DESPESA", category="ADMINISTRATIVO",
        budgeted_value=Decimal("2000"),
    )
    page = OrcamentoPage()
    qtbot.addWidget(page)
    controller = BudgetController(page, service)
    page.set_period(2026, 7)
    controller.refresh()
    assert page.table.rowCount() == 1
    assert page.budgeted_expense.text() == "R$ 2.000,00"
    assert page.actual_result.text() == "R$ 0,00"


def test_controller_creates_budget(qtbot, db_session, monkeypatch):
    service = make_service(db_session)
    page = OrcamentoPage()
    qtbot.addWidget(page)
    controller = BudgetController(page, service)
    page.set_period(2026, 7)

    class FakeDialog:
        def __init__(self, _parent, **_kwargs):
            self.year = StubField()
            self.month = StubField()

        def exec(self):
            return QDialog.DialogCode.Accepted

        def create_values(self):
            return 2026, 7, "DESPESA", "ADMINISTRATIVO", "Licenças", "2000.0000", "Teste"

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
        year=2026, month=7, entry_type="DESPESA", category="ADMINISTRATIVO",
        budgeted_value=Decimal("2000"),
    )
    page = OrcamentoPage()
    qtbot.addWidget(page)
    page.set_period(2026, 7)
    controller = BudgetController(page, service)
    controller.refresh()
    page.table.selectRow(0)

    class FakeDialog:
        def __init__(self, _parent, _budget, **_kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def update_values(self):
            return "Licenças anuais", "2500.0000", "Revisado"

    monkeypatch.setattr("app.gui.controllers.budget_controller.BudgetDialog", FakeDialog)
    controller.open_edit_dialog()
    assert service.get_budget(budget.id).valor_orcado == Decimal("2500.0000")
    assert service.get_budget(budget.id).observacao == "Revisado"
    assert service.get_budget(budget.id).descricao == "Licenças anuais"


def test_edit_preserves_inactive_historical_description(qtbot):
    budget = type("Budget", (), {
        "periodo_ano": 2026, "periodo_mes": 8, "tipo": "DESPESA",
        "categoria": "ADMINISTRATIVO", "descricao": "Fornecedor histórico",
        "valor_orcado": Decimal("100"), "observacao": None,
    })()
    dialog = BudgetDialog(
        budget=budget,
        catalog_options=(CashflowCatalogOption("Fornecedor ativo", "ADMINISTRATIVO", "DESPESA"),),
    )
    qtbot.addWidget(dialog)
    assert dialog.description.currentData() == "Fornecedor histórico"
    description, _, _ = dialog.update_values()
    assert description == "Fornecedor histórico"


def test_budget_controller_loads_local_catalog(qtbot, db_session, monkeypatch):
    catalog = CashflowCatalogService(CashflowCatalogRepository(db_session))
    catalog.create_entry(
        description="Licença local", category="ADMINISTRATIVO",
        movement_type="DESPESA",
    )
    page = OrcamentoPage()
    qtbot.addWidget(page)
    controller = BudgetController(page, make_service(db_session), catalog)
    captured = {}

    class FakeDialog:
        def __init__(self, _parent, **kwargs):
            captured["options"] = kwargs["catalog_options"]
            self.year = type("Field", (), {"setValue": lambda self, value: None})()
            self.month = type("Field", (), {"set_month": lambda self, value: None})()
        def exec(self): return QDialog.DialogCode.Rejected

    monkeypatch.setattr("app.gui.controllers.budget_controller.BudgetDialog", FakeDialog)
    controller.open_new_dialog()
    assert captured["options"][0].description == "Licença local"
