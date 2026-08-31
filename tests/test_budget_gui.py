from decimal import Decimal
import threading
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QAbstractItemView, QDialog

from app.api_client import APIConnectionError, APIReadTimeoutError
from app.gui.controllers.budget_controller import BudgetController
from app.gui.pages.orcamento import (
    BudgetDialog, BudgetImportProgressDialog, OrcamentoPage,
)
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository
from app.repositories.cashflow_catalog_repository import CashflowCatalogRepository
from app.services.budget_service import BudgetService, BudgetSummary, BudgetVsActual
from app.services.remote_services import RemoteBudgetService
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
    assert page.import_file_button.text() == "Importar Orçamento"


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


def test_budget_import_preview_enables_only_valid_confirmation(qtbot):
    page = OrcamentoPage()
    qtbot.addWidget(page)
    base = {
        "metadata": {
            "file_name": "orcamento.xlsx", "detected_type": "ORCAMENTO",
            "year": 2026,
        },
        "preview": [{
            "line": 9, "year": 2026, "month": 1,
            "entry_type": "RECEITA", "category": "RECEITA_DIRETA",
            "value": "200.0000", "source_label": "Repasse",
        }],
        "warnings": [], "totals": {"rows": 1, "value": "200.0000"},
    }

    page.show_import_validation({**base, "errors": [], "can_import": True})
    assert page.confirm_import_button.isEnabled()
    assert page.import_preview.rowCount() == 1
    assert page.import_preview.item(0, 6).text() == "Repasse"

    page.show_import_validation({
        **base, "errors": ["Duplicidade"], "can_import": False,
    })
    assert not page.confirm_import_button.isEnabled()
    assert "Duplicidade" in page.import_issues.text()


class _RemoteBudgetImportService:
    def __init__(self, *, error=None, wait=False):
        self.repository = SimpleNamespace(
            session=SimpleNamespace(rollback=lambda: None)
        )
        self.error = error
        self.wait = wait
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0
        self.worker_thread = None
        self.refresh_calls = 0
        self.validated_path = None

    def validate_import(self, path):
        self.validated_path = path
        return {
            "metadata": {
                "file_name": "orcamento.xlsx", "detected_type": "ORCAMENTO",
                "year": 2026,
            },
            "preview": [], "warnings": [], "errors": [],
            "can_import": True, "totals": {"rows": 1, "value": 200},
        }

    def import_file(self, _path):
        self.calls += 1
        self.worker_thread = threading.get_ident()
        self.started.set()
        if self.wait:
            self.release.wait(3)
        if self.error:
            raise self.error
        return {"imported": 2, "year": 2026, "total": "320.0000"}

    def get_budget_vs_actual(self, *_args):
        self.refresh_calls += 1
        zero = Decimal(0)
        return BudgetVsActual(
            (), BudgetSummary(zero, zero, zero, zero, zero, zero)
        )

    def list_by_year(self, _year):
        return []

    def list_by_period(self, _year, _month):
        return []


def _remote_controller(qtbot, service):
    page = OrcamentoPage()
    qtbot.addWidget(page)
    controller = BudgetController(page, service)
    controller.import_file_path = "orcamento.xlsx"
    page.confirm_import_button.setEnabled(True)
    return page, controller


def test_budget_controller_validates_selected_file(qtbot, monkeypatch):
    service = _RemoteBudgetImportService()
    page, controller = _remote_controller(qtbot, service)
    monkeypatch.setattr(
        "app.gui.controllers.budget_controller.QFileDialog.getOpenFileName",
        lambda *_args: ("selecionado.xlsx", "Planilhas Excel"),
    )

    controller.select_import_file()

    assert service.validated_path == "selecionado.xlsx"
    assert controller.import_file_path == "selecionado.xlsx"
    assert page.confirm_import_button.isEnabled()


def test_budget_import_runs_in_worker_blocks_duplicate_and_refreshes(qtbot):
    service = _RemoteBudgetImportService(wait=True)
    page, controller = _remote_controller(qtbot, service)
    main_thread = threading.get_ident()

    controller.import_validated_file()
    qtbot.waitUntil(service.started.is_set)

    assert service.worker_thread != main_thread
    assert not page.confirm_import_button.isEnabled()
    assert not page.import_file_button.isEnabled()
    assert isinstance(controller._import_dialog, BudgetImportProgressDialog)
    assert controller._import_dialog.isVisible()
    assert controller._import_dialog.windowTitle() == "Importação de Orçamento"
    assert controller._import_dialog.title.text() == "Processando importação..."
    assert controller._import_dialog.description.text() == (
        "Esta operação pode levar alguns instantes."
    )
    assert (
        controller._import_dialog.progress.minimum(),
        controller._import_dialog.progress.maximum(),
    ) == (0, 0)
    controller.import_validated_file()
    assert service.calls == 1

    service.release.set()
    qtbot.waitUntil(lambda: controller._import_thread is None)

    assert controller._import_dialog is None
    assert page.import_file_button.isEnabled()
    assert not page.confirm_import_button.isEnabled()
    assert "Orçamento importado com sucesso" in page.status.text()
    assert service.refresh_calls >= 2


@pytest.mark.parametrize(
    "error, message, confirmation_enabled",
    [
        (RuntimeError("falha segura"), "falha segura", True),
        (APIReadTimeoutError(
            "A importação está demorando mais que o esperado. "
            "Verifique o resultado antes de tentar novamente."
        ), "Verifique o resultado antes de tentar novamente", False),
        (APIConnectionError(
            "Servidor Finance indisponível. Verifique a conexão e tente novamente."
        ), "Servidor Finance indisponível", True),
    ],
)
def test_budget_import_error_closes_modal_and_restores_controls(
    qtbot, error, message, confirmation_enabled,
):
    service = _RemoteBudgetImportService(error=error)
    page, controller = _remote_controller(qtbot, service)

    controller.import_validated_file()
    qtbot.waitUntil(lambda: controller._import_thread is None)

    assert controller._import_dialog is None
    assert page.import_file_button.isEnabled()
    assert page.confirm_import_button.isEnabled() is confirmation_enabled
    assert message in page.status.text()
    if isinstance(error, APIReadTimeoutError):
        assert "Servidor Finance indisponível" not in page.status.text()


def test_remote_budget_import_uses_central_endpoints_and_import_timeout():
    class API:
        def __init__(self):
            self.calls = []

        def upload(self, path, file_path, **kwargs):
            self.calls.append((path, file_path, kwargs))
            return {"can_import": path.endswith("validate")}

    api = API()
    service = RemoteBudgetService(api)

    assert service.validate_import("orcamento.xlsx")["can_import"] is True
    service.import_file("orcamento.xlsx")
    assert api.calls == [
        ("/api/v1/budgets/import/validate", "orcamento.xlsx", {}),
        ("/api/v1/budgets/import", "orcamento.xlsx", {"import_file": True}),
    ]
