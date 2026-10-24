from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import BudgetDomainError
from app.api_client import APIClient, APIReadTimeoutError
from app.gui.processing import OperationWorker, ProcessingDialog
from app.gui.import_confirmation import confirm_import
from app.gui.pages.orcamento import (
    BudgetDialog, BudgetImportProgressDialog, OrcamentoPage,
)
from app.services.budget_service import BudgetService
from app.widgets.year_combo import AvailableYearsLoader


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
                 catalog_service=None, *,
                 defer_initial_load: bool = False) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self.catalog_service = catalog_service
        self.import_file_path = None
        self.selected_import_file_path = None
        self._last_import_validation: dict | None = None
        self._last_import_validation_path: str | None = None
        self._workflow_compared = False
        self._workflow_authorized_file: str | None = None
        self._pending_import_period: tuple[int, int | None] | None = None

        self._operation_thread: QThread | None = None
        self._operation_worker: OperationWorker | None = None
        self._operation_dialog = None
        self._import_thread: QThread | None = None
        self._import_worker: OperationWorker | None = None
        self._import_dialog = None

        self.view.filter_button.clicked.connect(self.refresh)
        self.view.new_button.clicked.connect(self.open_new_dialog)
        self.view.edit_button.clicked.connect(self.open_edit_dialog)
        self.view.import_steps.configure_actions(
            on_select=self.select_import_file,
            on_validate=self.validate_selected_import_file,
            on_compare=self.compare_import_validation,
            on_import=self.import_workflow_step,
        )
        self._reset_import_stages()

        import_available = (
            hasattr(service, "validate_import")
            and hasattr(service, "import_file")
        )
        self.view.set_import_available(import_available)
        self._years_loader = AvailableYearsLoader(
            self,
            self.service.available_years,
            self._years_loaded,
            lambda error: self.view.set_status(
                f"Falha ao carregar anos disponíveis: {error}", error=True
            ),
        )
        # JA_TECH_LAZY_ORCAMENTO_V1
        self._initial_load_started = False
        if not defer_initial_load:
            self.load_initial_data()

    def _years_loaded(self, years) -> None:
        self.view.set_available_years(years)
        pending = self._pending_import_period
        self._pending_import_period = None
        if pending is None:
            return
        year, month = pending
        self.view.set_period(year, month)
        self.refresh()

    def load_initial_data(self) -> None:
        """Load budget years on the first page visit."""
        if self._initial_load_started:
            return
        self._initial_load_started = True
        self._years_loader.load(remote=self._is_remote())

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

    def _invalidate_import_workflow(self) -> None:
        self._last_import_validation = None
        self._last_import_validation_path = None
        self._workflow_compared = False
        self._workflow_authorized_file = None
        for stage in range(3, 5):
            self._set_import_stage_enabled(stage, False)

    def reset_import_session(self) -> None:
        """Clear file-bound import state when the authenticated session ends."""
        self.import_file_path = None
        self.selected_import_file_path = None
        self._pending_import_period = None
        self._invalidate_import_workflow()
        self._reset_import_stages()
        self.view.import_summary.setText(
            "Selecione um arquivo para validar a importação de Orçamento."
        )
        self.view.import_issues.clear()
        self.view.import_preview.setRowCount(0)
        self.view.import_result.clear()

    def _set_import_stage_enabled(
        self, stage: int, enabled: bool
    ) -> None:
        self.view.import_steps.set_stage_enabled(
            stage,
            bool(enabled) and self.view.import_workflow_allowed,
        )

    def _reset_import_stages(self) -> None:
        for stage in range(1, 5):
            self.view.import_steps.set_stage_enabled(stage, False)
        self._set_import_stage_enabled(1, True)

    def _restore_import_entry_stages(self) -> None:
        self._set_import_stage_enabled(1, True)
        self._set_import_stage_enabled(
            2, self.selected_import_file_path is not None
        )

    def select_import_file(self) -> None:
        if not self.view.import_workflow_allowed:
            return

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
        self._invalidate_import_workflow()
        self._reset_import_stages()
        self._set_import_stage_enabled(2, True)

        self.view.import_summary.setText(
            f"Arquivo selecionado: {Path(path).name}"
        )
        self.view.import_issues.setText("")
        self.view.set_status("Arquivo selecionado. Clique em Validar.")

    def validate_selected_import_file(self) -> None:
        if not self.selected_import_file_path:
            return

        self.validate_import_file(self.selected_import_file_path)

    def validate_import_file(self, path: str) -> None:
        if not self.view.import_workflow_allowed:
            return
        if (
            self._operation_thread is not None
            and self._operation_thread.isRunning()
        ):
            return

        self.import_file_path = None
        self._invalidate_import_workflow()
        self._set_import_stage_enabled(1, False)
        self._set_import_stage_enabled(2, False)

        def succeeded(validation: dict) -> None:
            if self.selected_import_file_path != path:
                self._restore_import_entry_stages()
                return
            if not isinstance(validation, dict) or not validation:
                self.view.set_status(
                    "A validação do Orçamento não retornou um resultado utilizável.",
                    error=True,
                )
                self._restore_import_entry_stages()
                return
            self.view.show_import_validation(validation)
            self._restore_import_entry_stages()
            self._last_import_validation = validation
            self._last_import_validation_path = path
            self._set_import_stage_enabled(3, True)

            if validation.get("can_import"):
                self.import_file_path = path

        def failed(error: Exception) -> None:
            if self.selected_import_file_path != path:
                self._restore_import_entry_stages()
                return
            self._invalidate_import_workflow()
            self.view.set_status(
                f"Falha ao validar arquivo de Or\u00e7amento: {error}",
                error=True,
            )
            self._restore_import_entry_stages()

        self._run_operation(
            window_title="Valida\u00e7\u00e3o do Or\u00e7amento",
            operation=lambda: self.service.validate_import(path),
            succeeded=succeeded,
            failed=failed,
        )

    def compare_import_validation(self) -> None:
        """Display differences and accept an explicit import authorization."""
        from PySide6.QtWidgets import QDialog
        from app.gui.budget_comparison_dialog import BudgetComparisonDialog

        validation = self._last_import_validation
        selected_file = self.selected_import_file_path

        self._workflow_compared = False
        self._workflow_authorized_file = None
        self._set_import_stage_enabled(4, False)

        if not self.view.import_workflow_allowed:
            return

        is_current = (
            validation is not None
            and selected_file is not None
            and self._last_import_validation_path == selected_file
            and self.import_file_path == selected_file
        )
        if not is_current:
            self.view.set_status(
                "Valide o arquivo de Or\u00e7amento antes de comparar.",
                error=True,
            )
            return

        comparison_rows = validation.get("comparison_preview") or []
        has_changes = any(
            isinstance(row, dict)
            and row.get("status") in ("NEW", "CHANGED")
            for row in comparison_rows
        )
        totals = validation.get("comparison_totals") or {}
        counted_changes = (
            int(totals.get("new") or 0)
            + int(totals.get("changed") or 0)
        )

        eligible = (
            bool(validation.get("can_import"))
            and has_changes
            and counted_changes > 0
        )
        dialog = BudgetComparisonDialog(
            validation,
            can_authorize=eligible,
            parent=self.view,
        )
        decision = dialog.exec()

        still_current = (
            self.selected_import_file_path == selected_file
            and self.import_file_path == selected_file
            and self._last_import_validation_path == selected_file
            and self._last_import_validation is validation
        )

        if (
            decision == QDialog.DialogCode.Accepted
            and eligible
            and still_current
        ):
            self._workflow_compared = True
            self._workflow_authorized_file = selected_file
            self._set_import_stage_enabled(4, True)
            self.view.set_status(
                "Altera\u00e7\u00f5es autorizadas. "
                "Etapa Importar liberada."
            )
        else:
            self.view.set_status(
                "Compara\u00e7\u00e3o encerrada sem "
                "autoriza\u00e7\u00e3o."
            )



    def import_workflow_step(self) -> None:
        """Run the existing mandatory final import confirmation."""
        self.confirm_and_import()


    def confirm_and_import(self) -> None:
        """Apenas a interação da interface exige confirmação modal."""
        authorized_file = self._workflow_authorized_file
        self._workflow_authorized_file = None
        self._set_import_stage_enabled(4, False)
        selected_file = self.selected_import_file_path
        validation = self._last_import_validation
        eligible = (
            authorized_file is not None
            and authorized_file == selected_file
            and self._workflow_compared
            and validation is not None
            and bool(validation.get("can_import"))
            and self._last_import_validation_path == selected_file
            and self.import_file_path == selected_file
            and self.view.import_workflow_allowed
        )
        if not eligible:
            self.view.set_status(
                "Confirme novamente o fluxo de Orçamento antes de importar.",
                error=True,
            )
            return
        if not confirm_import(self.view, module_name="Orçamento"):
            self.view.set_status(
                "Importação cancelada. Nenhum dado enviado."
            )
            return
        self.import_validated_file()

    def import_validated_file(self) -> None:
        if not self.view.import_workflow_allowed:
            return
        if not self.import_file_path or (
            self._import_thread is not None
            and self._import_thread.isRunning()
        ):
            return

        selected_file = self.import_file_path
        _, selected_month = self.view.selected_period()

        for stage in range(1, 5):
            self._set_import_stage_enabled(stage, False)

        def operation():
            return self.service.import_file(selected_file)

        def succeeded(result) -> None:
            self.view.show_import_result(result)
            self.import_file_path = None
            self.selected_import_file_path = None
            self._invalidate_import_workflow()
            self._reset_import_stages()
            imported_year = result.get("year") if isinstance(result, dict) else None
            if imported_year is not None:
                self._pending_import_period = (int(imported_year), selected_month)
            self._years_loader.load(remote=self._is_remote())

        def failed(error: Exception) -> None:
            if isinstance(error, APIReadTimeoutError):
                self.import_file_path = None
                self._invalidate_import_workflow()

            self.view.set_status(
                f"Falha ao importar Or\u00e7amento: {error}",
                error=True,
            )
            self._restore_import_entry_stages()
            can_compare = (
                self._last_import_validation is not None
                and self._last_import_validation_path
                == self.selected_import_file_path
                and self.import_file_path
                == self.selected_import_file_path
            )
            self._set_import_stage_enabled(3, can_compare)
            self._set_import_stage_enabled(4, False)

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
            if year is not None:
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
