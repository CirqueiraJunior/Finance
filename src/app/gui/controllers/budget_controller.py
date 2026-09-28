from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import BudgetDomainError
from app.api_client import APIClient, APIReadTimeoutError
from app.gui.processing import OperationWorker, ProcessingDialog
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
        self.selected_import_file_path = None

        self._operation_thread: QThread | None = None
        self._operation_worker: OperationWorker | None = None
        self._operation_dialog = None
        self._import_thread: QThread | None = None
        self._import_worker: OperationWorker | None = None
        self._import_dialog = None

        self.view.filter_button.clicked.connect(self.refresh)
        self.view.new_button.clicked.connect(self.open_new_dialog)
        self.view.edit_button.clicked.connect(self.open_edit_dialog)
        self.view.import_file_button.clicked.connect(self.select_import_file)
        self.view.validate_import_button.clicked.connect(
            self.validate_selected_import_file
        )
        self.view.confirm_import_button.clicked.connect(
            self.import_validated_file
        )

        self.view.set_import_available(
            hasattr(service, "validate_import")
            and hasattr(service, "import_file")
        )

        # A carga inicial da MainWindow já possui ProcessingDialog próprio.
        # Evita abrir um segundo diálogo "Orçamento" durante o pós-login.

    def _is_remote(self) -> bool:
        return isinstance(getattr(self.service, "api", None), APIClient)

    def _rollback_local(self) -> None:
        repository = getattr(self.service, "repository", None)
        session = getattr(repository, "session", None)

        if session is not None:
            try:
                session.rollback()
            except Exception:
                pass

    def _run_operation(
        self,
        *,
        window_title: str,
        operation,
        succeeded,
        failed,
        dialog_factory=None,
        force_worker: bool = False,
        import_operation: bool = False,
    ) -> None:
        repository = getattr(self.service, "repository", None)
        local_session = getattr(repository, "session", None)

        # Uma Session SQLAlchemy real nunca atravessa threads.
        # Nos demais casos, force_worker permite executar operacoes
        # explicitamente demoradas, como importacao, em background.
        if (
            isinstance(local_session, Session)
            or (
                not force_worker
                and not self._is_remote()
            )
        ):
            try:
                succeeded(operation())
            except Exception as error:
                self._rollback_local()
                failed(error)
            return

        if (
            self._operation_thread is not None
            and self._operation_thread.isRunning()
        ):
            return

        if dialog_factory is None:
            dialog = ProcessingDialog(
                self.view,
                window_title=window_title,
            )
        else:
            dialog = dialog_factory()

        thread = QThread(self)
        worker = OperationWorker(operation)
        worker.moveToThread(thread)

        self._operation_dialog = dialog
        self._operation_thread = thread
        self._operation_worker = worker

        if import_operation:
            self._import_dialog = dialog
            self._import_thread = thread
            self._import_worker = worker

        state = {
            "result": None,
            "error": None,
            "ok": False,
        }

        def store_success(result) -> None:
            state["result"] = result
            state["ok"] = True

        def store_failure(error) -> None:
            state["error"] = error

        def finished() -> None:
            if self._operation_dialog is not None:
                self._operation_dialog.accept()
                self._operation_dialog.deleteLater()

            if self._operation_thread is not None:
                self._operation_thread.deleteLater()

            self._operation_dialog = None
            self._operation_thread = None
            self._operation_worker = None

            if import_operation:
                self._import_dialog = None
                self._import_thread = None
                self._import_worker = None

            if state["ok"]:
                succeeded(state["result"])
            else:
                failed(state["error"])

        thread.started.connect(worker.run)
        worker.succeeded.connect(store_success)
        worker.failed.connect(store_failure)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(finished)

        dialog.show()
        thread.start()

    def _load_period(self, year: int, month: int | None):
        result = self.service.get_budget_vs_actual(year, month)

        budgets = (
            self.service.list_by_year(year)
            if month is None
            else self.service.list_by_period(year, month)
        )

        return result, budgets

    def _show_period(self, payload) -> None:
        result, budgets = payload
        self.view.show_result(result, budgets)

    def _period_failed(self, error: Exception) -> None:
        self._rollback_local()
        self.view.set_status(
            f"Falha ao carregar or\u00e7amento: {error}",
            error=True,
        )

    def select_import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.view,
            "Selecionar arquivo de Orçamento",
            "",
            "Planilhas Excel (*.xlsx *.xlsm)",
        )

        if not path:
            return

        self.selected_import_file_path = path
        self.import_file_path = None

        self.view.import_summary.setText(
            f"Arquivo selecionado: {Path(path).name}"
        )
        self.view.import_issues.setText("")
        self.view.validate_import_button.setEnabled(True)
        self.view.confirm_import_button.setEnabled(False)
        self.view.set_status("Arquivo selecionado. Clique em Validar.")

    def validate_selected_import_file(self) -> None:
        if not self.selected_import_file_path:
            return

        self.validate_import_file(self.selected_import_file_path)

    def validate_import_file(self, path: str) -> None:
        self.import_file_path = None
        self.view.validate_import_button.setEnabled(False)
        self.view.confirm_import_button.setEnabled(False)

        def succeeded(validation: dict) -> None:
            self.view.show_import_validation(validation)
            self.view.validate_import_button.setEnabled(True)

            if validation.get("can_import"):
                self.import_file_path = path
                self.view.confirm_import_button.setEnabled(True)

        def failed(error: Exception) -> None:
            self.view.set_status(
                f"Falha ao validar arquivo de Or\u00e7amento: {error}",
                error=True,
            )
            self.view.validate_import_button.setEnabled(
                self.selected_import_file_path is not None
            )

        self._run_operation(
            window_title="Valida\u00e7\u00e3o do Or\u00e7amento",
            operation=lambda: self.service.validate_import(path),
            succeeded=succeeded,
            failed=failed,
        )

    def import_validated_file(self) -> None:
        if not self.import_file_path or (
            self._import_thread is not None
            and self._import_thread.isRunning()
        ):
            return

        selected_file = self.import_file_path
        selected_year, selected_month = self.view.selected_period()

        self.view.confirm_import_button.setEnabled(False)
        self.view.validate_import_button.setEnabled(False)
        self.view.import_file_button.setEnabled(False)

        def operation():
            result = self.service.import_file(selected_file)

            period = self._load_period(
                selected_year,
                selected_month,
            )

            return result, period

        def succeeded(payload) -> None:
            result, period = payload

            self.view.show_import_result(result)
            self.import_file_path = None
            self.selected_import_file_path = None
            self._show_period(period)

            self.view.import_file_button.setEnabled(True)
            self.view.validate_import_button.setEnabled(False)
            self.view.confirm_import_button.setEnabled(False)

        def failed(error: Exception) -> None:
            if isinstance(error, APIReadTimeoutError):
                self.import_file_path = None

            self.view.set_status(
                f"Falha ao importar Or\u00e7amento: {error}",
                error=True,
            )

            self.view.import_file_button.setEnabled(True)
            self.view.validate_import_button.setEnabled(
                self.selected_import_file_path is not None
            )
            self.view.confirm_import_button.setEnabled(
                self.import_file_path is not None
            )

        self._run_operation(
            window_title="Importa\u00e7\u00e3o do Or\u00e7amento",
            operation=operation,
            succeeded=succeeded,
            failed=failed,
            dialog_factory=lambda: BudgetImportProgressDialog(
                self.view
            ),
            force_worker=True,
            import_operation=True,
        )

    def refresh(self) -> None:
        year, month = self.view.selected_period()

        self._run_operation(
            window_title="Or\u00e7amento",
            operation=lambda: self._load_period(year, month),
            succeeded=self._show_period,
            failed=self._period_failed,
        )

    def open_new_dialog(self) -> None:
        def load_options():
            if self.catalog_service is None:
                return ()

            return self.catalog_service.list_budget_options()

        def options_loaded(options) -> None:
            dialog = BudgetDialog(
                self.view,
                catalog_options=options,
            )

            year, month = self.view.selected_period()
            dialog.year.setValue(year)

            if month is not None:
                dialog.month.set_month(month)

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            values = dialog.create_values()
            self._create_budget(values)

        def failed(error: Exception) -> None:
            self.view.set_status(
                f"Falha ao carregar Cat\u00e1logo: {error}",
                error=True,
            )

        self._run_operation(
            window_title="Novo Or\u00e7amento",
            operation=load_options,
            succeeded=options_loaded,
            failed=failed,
        )

    def _create_budget(self, values) -> None:
        (
            year,
            month,
            entry_type,
            category,
            description,
            value,
            notes,
        ) = values

        def operation():
            self.service.create_budget(
                year=year,
                month=month,
                entry_type=entry_type,
                category=category,
                descricao=description,
                budgeted_value=value,
                notes=notes,
            )

            selected_year, selected_month = self.view.selected_period()

            return self._load_period(
                selected_year,
                selected_month,
            )

        def succeeded(period) -> None:
            self._show_period(period)
            self.view.set_status(
                "Or\u00e7amento cadastrado com sucesso."
            )

        def failed(error: Exception) -> None:
            self.view.set_status(
                str(error),
                error=True,
            )

        self._run_operation(
            window_title="Salvando Or\u00e7amento",
            operation=operation,
            succeeded=succeeded,
            failed=failed,
        )

    def open_edit_dialog(self) -> None:
        budget_id = self.view.selected_budget_id()

        if budget_id is None:
            self.view.set_status(
                "Selecione uma linha com or\u00e7amento para editar.",
                error=True,
            )
            return

        def load_data():
            budget = self.service.get_budget(budget_id)

            options = (
                self.catalog_service.list_budget_options()
                if self.catalog_service
                else ()
            )

            return budget, options

        def loaded(payload) -> None:
            budget, options = payload

            if budget is None:
                self.view.set_status(
                    "Or\u00e7amento n\u00e3o encontrado.",
                    error=True,
                )
                return

            dialog = BudgetDialog(
                self.view,
                budget,
                catalog_options=options,
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            self._update_budget(
                budget.id,
                dialog.update_values(),
            )

        def failed(error: Exception) -> None:
            self.view.set_status(
                f"Falha ao carregar Or\u00e7amento: {error}",
                error=True,
            )

        self._run_operation(
            window_title="Editar Or\u00e7amento",
            operation=load_data,
            succeeded=loaded,
            failed=failed,
        )

    def _update_budget(self, budget_id: int, values) -> None:
        description, value, notes = values

        def operation():
            self.service.update_budget(
                budget_id,
                descricao=description,
                budgeted_value=value,
                notes=notes,
            )

            year, month = self.view.selected_period()

            return self._load_period(year, month)

        def succeeded(period) -> None:
            self._show_period(period)
            self.view.set_status(
                "Or\u00e7amento atualizado com sucesso."
            )

        def failed(error: Exception) -> None:
            self.view.set_status(
                str(error),
                error=True,
            )

        self._run_operation(
            window_title="Atualizando Or\u00e7amento",
            operation=operation,
            succeeded=succeeded,
            failed=failed,
        )
