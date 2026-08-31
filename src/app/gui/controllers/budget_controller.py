from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import BudgetDomainError
from app.api_client import APIReadTimeoutError
from app.gui.pages.orcamento import (
    BudgetDialog, BudgetImportProgressDialog, OrcamentoPage,
)
from app.services.budget_service import BudgetService


class BudgetImportWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, service, file_path: str) -> None:
        super().__init__()
        self.service = service
        self.file_path = file_path

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(self.service.import_file(self.file_path))
        except Exception as error:
            self.failed.emit(error)
        finally:
            self.finished.emit()


class BudgetController(QObject):
    def __init__(self, view: OrcamentoPage, service: BudgetService,
                 catalog_service=None) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self.catalog_service = catalog_service
        self.import_file_path = None
        self._import_thread: QThread | None = None
        self._import_worker: BudgetImportWorker | None = None
        self._import_dialog: BudgetImportProgressDialog | None = None
        self.view.filter_button.clicked.connect(self.refresh)
        self.view.new_button.clicked.connect(self.open_new_dialog)
        self.view.edit_button.clicked.connect(self.open_edit_dialog)
        self.view.import_file_button.clicked.connect(self.select_import_file)
        self.view.confirm_import_button.clicked.connect(self.import_validated_file)
        self.view.set_import_available(
            hasattr(service, "validate_import") and hasattr(service, "import_file")
        )
        self.refresh()

    def select_import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.view, "Selecionar arquivo de Orçamento", "",
            "Planilhas Excel (*.xlsx *.xlsm)",
        )
        if path:
            self.validate_import_file(path)

    def validate_import_file(self, path: str) -> None:
        self.import_file_path = None
        self.view.confirm_import_button.setEnabled(False)
        try:
            validation = self.service.validate_import(path)
            self.view.show_import_validation(validation)
            if validation.get("can_import"):
                self.import_file_path = path
        except RuntimeError as error:
            self.view.set_status(
                f"Falha ao validar arquivo de Orçamento: {error}", error=True
            )

    def import_validated_file(self) -> None:
        if not self.import_file_path or (
            self._import_thread is not None and self._import_thread.isRunning()
        ):
            return
        self.view.confirm_import_button.setEnabled(False)
        self.view.import_file_button.setEnabled(False)
        self._import_dialog = BudgetImportProgressDialog(self.view)
        self._import_dialog.show()
        self._import_thread = QThread(self)
        self._import_worker = BudgetImportWorker(
            self.service, self.import_file_path
        )
        self._import_worker.moveToThread(self._import_thread)
        self._import_thread.started.connect(self._import_worker.run)
        self._import_worker.succeeded.connect(self._import_succeeded)
        self._import_worker.failed.connect(self._import_failed)
        self._import_worker.finished.connect(self._import_thread.quit)
        self._import_worker.finished.connect(self._import_worker.deleteLater)
        self._import_thread.finished.connect(self._import_finished)
        self._import_thread.start()

    @Slot(object)
    def _import_succeeded(self, result: dict) -> None:
        self.view.show_import_result(result)
        self.import_file_path = None
        self.refresh()

    @Slot(object)
    def _import_failed(self, error: Exception) -> None:
        if isinstance(error, APIReadTimeoutError):
            self.import_file_path = None
        self.view.set_status(
            f"Falha ao importar Orçamento: {error}", error=True
        )

    @Slot()
    def _import_finished(self) -> None:
        if self._import_dialog is not None:
            self._import_dialog.accept()
            self._import_dialog.deleteLater()
            self._import_dialog = None
        if self._import_thread is not None:
            self._import_thread.deleteLater()
        self._import_thread = None
        self._import_worker = None
        self.view.import_file_button.setEnabled(True)
        self.view.confirm_import_button.setEnabled(
            self.import_file_path is not None
        )

    def refresh(self) -> None:
        year, month = self.view.selected_period()
        try:
            result = self.service.get_budget_vs_actual(year, month)
            budgets = (
                self.service.list_by_year(year)
                if month is None else self.service.list_by_period(year, month)
            )
            self.view.show_result(result, budgets)
        except (BudgetDomainError, SQLAlchemyError, RuntimeError) as error:
            self.service.repository.session.rollback()
            self.view.set_status(f"Falha ao carregar orçamento: {error}", error=True)

    def open_new_dialog(self) -> None:
        try:
            options = self.catalog_service.list_budget_options() if self.catalog_service else ()
        except RuntimeError as error:
            self.view.set_status(f"Falha ao carregar Catálogo: {error}", error=True)
            return
        dialog = BudgetDialog(self.view, catalog_options=options)
        year, month = self.view.selected_period()
        dialog.year.setValue(year)
        if month is not None:
            dialog.month.set_month(month)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        year, month, entry_type, category, description, value, notes = dialog.create_values()
        try:
            self.service.create_budget(
                year=year, month=month, entry_type=entry_type, category=category,
                descricao=description, budgeted_value=value, notes=notes,
            )
        except (BudgetDomainError, RuntimeError) as error:
            self.view.set_status(str(error), error=True)
            return
        self.view.set_status("Orçamento cadastrado com sucesso.")
        self.refresh()

    def open_edit_dialog(self) -> None:
        budget_id = self.view.selected_budget_id()
        if budget_id is None:
            self.view.set_status("Selecione uma linha com orçamento para editar.", error=True)
            return
        budget = self.service.get_budget(budget_id)
        if budget is None:
            self.view.set_status("Orçamento não encontrado.", error=True)
            return
        try:
            options = self.catalog_service.list_budget_options() if self.catalog_service else ()
        except RuntimeError as error:
            self.view.set_status(f"Falha ao carregar Catálogo: {error}", error=True)
            return
        dialog = BudgetDialog(self.view, budget, catalog_options=options)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        description, value, notes = dialog.update_values()
        try:
            self.service.update_budget(
                budget.id, descricao=description, budgeted_value=value, notes=notes
            )
        except (BudgetDomainError, RuntimeError) as error:
            self.view.set_status(str(error), error=True)
            return
        self.view.set_status("Orçamento atualizado com sucesso.")
        self.refresh()
