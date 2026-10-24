from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QFileDialog, QMessageBox
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import BOEDomainError, BOEValidationError
from app.gui.pages.boe import BoePage
from app.gui.processing import OperationWorker, ProcessingDialog
from app.services.boe_service import BOEService


class BOEController(QObject):
    import_completed = Signal()

    def __init__(self, view: BoePage, service: BOEService, *, defer_initial_load: bool = False) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self._selected_file: Path | None = None
        self._validated_boe = None
        self._last_boe_preview = None
        self._boe_step_confirmed = False
        self.view.import_steps.buttons[3].clicked.connect(
            self.import_step
        )
        self._boe_validation_generation = 0
        self._import_thread: QThread | None = None
        self._import_worker: OperationWorker | None = None
        self._import_dialog: ProcessingDialog | None = None
        self._operation_thread: QThread | None = None
        self._operation_worker: OperationWorker | None = None
        self._operation_dialog: ProcessingDialog | None = None
        self.view.import_steps.buttons[0].setEnabled(True)
        self.view.import_steps.buttons[0].clicked.connect(
            self.select_file
        )
        self.view.import_steps.buttons[1].clicked.connect(
            self.validate_file
        )
        self.view.import_steps.buttons[2].clicked.connect(
            self.compare_file
        )
        self.view.history_table.itemSelectionChanged.connect(
            self.load_selected_details
        )
        self.view.query_button.clicked.connect(self.query_operations)
        # The five-step toolbar is the sole visible import workflow.
        # Keep legacy widgets wired for compatibility.

        # JA_TECH_LAZY_BOE_V1
        self._initial_load_started = False
        if not defer_initial_load:
            self.load_initial_data()

    def load_initial_data(self) -> None:
        """Load BOE data once, when the page is first accessed."""
        if self._initial_load_started:
            return
        self._initial_load_started = True
        self.refresh_history()
        self.refresh_operational_entities()

    def reset_import_session(self) -> None:
        """Discard the selected workbook and its transient authorization."""
        self._boe_validation_generation += 1
        self._selected_file = None
        self._validated_boe = None
        self._last_boe_preview = None
        self._boe_step_confirmed = False
        self.view.file_path.clear()
        self.view.clear_validation_preview()
        self.view.clear_import_result()
        self.view.import_steps.reset_stages()
        self.view.import_steps.set_stage_enabled(
            1, getattr(self.view, "_boe_write_allowed", True)
        )
        self.view.set_status("Selecione um arquivo para iniciar.")

    def _run_operation(
        self,
        *,
        window_title: str,
        operation,
        succeeded,
        failed,
        import_operation: bool = False,
    ) -> None:
        repository = getattr(self.service, "repository", None)
        local_session = getattr(repository, "session", None)

        # Apenas uma Session SQLAlchemy real fica na thread da GUI.
        # Serviço remoto e stubs sem Session real podem usar worker.
        if (
            isinstance(local_session, Session)
            or (
                not hasattr(self.service, "api")
                and not import_operation
            )
        ):
            try:
                succeeded(operation())
            except Exception as error:
                failed(error)
            return

        if (
            self._operation_thread is not None
            and self._operation_thread.isRunning()
        ):
            return

        self._operation_dialog = ProcessingDialog(
            self.view,
            window_title=window_title,
        )
        self._operation_thread = QThread(self)
        self._operation_worker = OperationWorker(operation)
        self._operation_worker.moveToThread(
            self._operation_thread
        )

        if import_operation:
            self._import_dialog = self._operation_dialog
            self._import_thread = self._operation_thread
            self._import_worker = self._operation_worker

        def finished() -> None:
            if self._operation_dialog is not None:
                self._operation_dialog.accept()
                self._operation_dialog.deleteLater()
                self._operation_dialog = None

            if self._operation_thread is not None:
                self._operation_thread.deleteLater()

            self._operation_thread = None
            self._operation_worker = None

            if import_operation:
                self._import_dialog = None
                self._import_thread = None
                self._import_worker = None

        self._operation_thread.started.connect(
            self._operation_worker.run
        )
        self._operation_worker.succeeded.connect(succeeded)
        self._operation_worker.failed.connect(failed)
        self._operation_worker.finished.connect(
            self._operation_thread.quit
        )
        self._operation_worker.finished.connect(
            self._operation_worker.deleteLater
        )
        self._operation_thread.finished.connect(finished)

        self._operation_dialog.show()
        self._operation_thread.start()

    def select_file(self) -> None:
        if not getattr(self.view, "_boe_write_allowed", True):
            return
        if (
            self._import_thread is not None
            and self._import_thread.isRunning()
        ):
            return

        selected, _ = QFileDialog.getOpenFileName(
            self.view, "Selecionar arquivo BOE", "",
            "Planilhas Excel (*.xlsx)",
        )
        if not selected:
            return

        self._boe_validation_generation += 1
        self._selected_file = Path(selected)
        self._validated_boe = None
        self._last_boe_preview = None
        self._boe_step_confirmed = False

        self.view.import_steps.reset_stages()
        self.view.import_steps.set_stage_enabled(2, True)
        self.view.file_path.setText(selected)
        self.view.clear_validation_preview()
        self.view.clear_import_result()
        self.view.set_status(
            "Arquivo selecionado. Execute a validação."
        )


    def validate_file(self) -> None:
        if not getattr(self.view, "_boe_write_allowed", True):
            return
        if self._selected_file is None:
            return
        if (
            self._import_thread is not None
            and self._import_thread.isRunning()
        ):
            return

        self._boe_validation_generation += 1
        generation = self._boe_validation_generation
        selected = self._selected_file

        self._validated_boe = None
        self._last_boe_preview = None
        self._boe_step_confirmed = False
        self.view.import_steps.set_stage_enabled(3, False)
        self.view.import_steps.set_stage_enabled(4, False)

        def succeeded(result) -> None:
            if (
                self._selected_file != selected
                or self._boe_validation_generation != generation
            ):
                return

            self._last_boe_preview = result
            self._validated_boe = (
                result if result.aprovado else None
            )
            self.view.show_validation(result)
            self.view.import_steps.set_stage_enabled(3, True)
            self.view.set_status(
                "Validação aprovada. Compare a BOE."
                if result.aprovado
                else "Validação reprovada. Consulte as inconsistências.",
                error=not result.aprovado,
            )

        def failed(error: Exception) -> None:
            if generation != self._boe_validation_generation:
                return
            self._validated_boe = None
            self._last_boe_preview = None
            self._boe_step_confirmed = False
            self.view.import_steps.set_stage_enabled(3, False)
            self.view.import_steps.set_stage_enabled(4, False)
            self.view.set_status(
                f"Falha ao validar: {error}", error=True
            )

        self._run_operation(
            window_title="Validação BOE",
            operation=lambda: self.service.validate_file(selected),
            succeeded=succeeded,
            failed=failed,
        )


    def compare_file(self) -> None:
        from PySide6.QtWidgets import QDialog
        from app.gui.boe_comparison_dialog import BOEComparisonDialog

        self._boe_step_confirmed = False
        self.view.import_steps.set_stage_enabled(4, False)

        result = self._last_boe_preview
        if result is None:
            self.view.set_status(
                "Valide a BOE antes de comparar.", error=True
            )
            return

        selected = self._selected_file
        preview_path = getattr(result, "caminho_arquivo", None)
        eligible = (
            bool(getattr(result, "aprovado", False))
            and not bool(getattr(result, "quantidade_erros", 0))
            and selected is not None
            and preview_path is not None
            and Path(preview_path).resolve() == selected.resolve()
            and self._validated_boe is result
            and getattr(self.view, "_boe_write_allowed", True)
        )
        generation = self._boe_validation_generation

        dialog = BOEComparisonDialog(
            result, can_authorize=eligible, parent=self.view
        )
        accepted = dialog.exec() == QDialog.DialogCode.Accepted

        still_valid = (
            eligible
            and self._selected_file == selected
            and generation == self._boe_validation_generation
            and self._last_boe_preview is result
            and self._validated_boe is result
            and getattr(self.view, "_boe_write_allowed", True)
        )

        if not (
            accepted and still_valid
            and dialog.authorize_button is not None
        ):
            self.view.set_status(
                "Comparação encerrada sem autorização."
            )
            return

        self._boe_step_confirmed = True
        self.view.import_steps.set_stage_enabled(4, True)
        self.view.set_status(
            "Comparação autorizada. Etapa Importar liberada."
        )



    def import_step(self) -> None:
        preview = self._validated_boe
        selected = self._selected_file

        authorized = (
            self._boe_step_confirmed
            and preview is not None
            and bool(getattr(preview, "aprovado", False))
            and not bool(getattr(preview, "quantidade_erros", 0))
            and selected is not None
            and Path(preview.caminho_arquivo).resolve()
                == selected.resolve()
            and getattr(self.view, "_boe_write_allowed", True)
            and not (
                self._import_thread is not None
                and self._import_thread.isRunning()
            )
        )

        # Autorizacao de uso unico.
        self._boe_step_confirmed = False
        self.view.import_steps.set_stage_enabled(4, False)

        if not authorized:
            self.view.set_status(
                "Compare e autorize novamente antes de importar.",
                error=True,
            )
            return

        # Confirmacao final e revalidacao permanecem em import_file().
        self.import_file()


    def import_file(self) -> None:
        self._boe_step_confirmed = False
        self.view.import_steps.set_stage_enabled(4, False)
        if self._selected_file is None:
            return

        # Never allow a second operation while an import is running.
        if (
            self._import_thread is not None
            and self._import_thread.isRunning()
        ):
            return

        preview = self._validated_boe
        if (
            preview is None
            or not preview.aprovado
            or preview.caminho_arquivo.resolve()
               != self._selected_file.resolve()
        ):
            self.view.set_status(
                "Valide novamente a BOE antes de importar.",
                error=True,
            )
            return

        period = (
            f"{preview.periodo_mes:02d}/{preview.periodo_ano}"
            if preview.periodo_mes is not None
            and preview.periodo_ano is not None
            else "Não identificado"
        )
        message = (
            f"Competência: {period}\n"
            f"Arquivo: {preview.nome_arquivo}\n"
            f"Entidades: {len(preview.linhas)}\n"
            f"Valor: {self.view._format_currency(preview.valor_total_calculado)}\n"
            f"Avisos: {preview.quantidade_avisos}\n\n"
            "A BOE será registrada e gerará a Receita Direta "
            "correspondente no Financeiro.\n"
            "Uma competência já importada não poderá ser substituída.\n\n"
            "Confirma esta importação?"
        )
        dialog = QMessageBox(self.view)
        dialog.setWindowTitle("Confirmar importa\u00e7\u00e3o BOE")
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setText(message)
        cancel_button = dialog.addButton(
            "Cancelar", QMessageBox.ButtonRole.RejectRole
        )
        confirm_button = dialog.addButton(
            "Confirmar importa\u00e7\u00e3o",
            QMessageBox.ButtonRole.AcceptRole,
        )
        dialog.setDefaultButton(cancel_button)
        dialog.exec()
        if dialog.clickedButton() is not confirm_button:
            self.view.set_status(
                "Importação cancelada. Nenhum dado gravado."
            )
            return

        # A service/server revalidation is mandatory at import time.
        self._validated_boe = None
        selected_file = self._selected_file

        self.view.import_steps.set_stage_enabled(1, False)
        self.view.import_steps.set_stage_enabled(2, False)
        self.view.import_steps.set_stage_enabled(3, False)
        self.view.import_steps.set_stage_enabled(4, False)

        def operation():
            imported = self.service.import_file(selected_file)
            history = self.service.list_imports()

            entities = (
                self.service.list_operational_entities()
                if hasattr(
                    self.service,
                    "list_operational_entities",
                )
                else ()
            )

            return imported, history, entities

        def succeeded(result) -> None:
            imported, history, entities = result

            self.view.show_import_success(imported)
            self.view.show_history(history)
            self.view.set_operational_entities(entities)

            self.view.set_status(
                (
                    f"BOE {imported.periodo_mes:02d}/"
                    f"{imported.periodo_ano} importado com sucesso."
                )
            )
            self.import_completed.emit()

            allowed = getattr(
                self.view, "_boe_write_allowed", True
            )
            self.view.import_steps.set_stage_enabled(1, allowed)
            self.view.import_steps.set_stage_enabled(
                2, allowed and self._selected_file is not None
            )
            self.view.import_steps.set_stage_enabled(3, False)
            self.view.import_steps.set_stage_enabled(4, False)

            # Toda nova tentativa exige nova validacao.

        def failed(error: Exception) -> None:
            if isinstance(error, BOEValidationError):
                self.view.show_validation(error.result)
                self.view.show_import_error(str(error))
                self.view.set_status(
                    str(error),
                    error=True,
                )
            elif isinstance(error, BOEDomainError):
                self.view.show_import_error(str(error))
                self.view.set_status(
                    str(error),
                    error=True,
                )
            else:
                self.view.show_import_error(str(error))
                self.view.set_status(
                    f"Falha ao importar: {error}",
                    error=True,
                )

            allowed = getattr(
                self.view, "_boe_write_allowed", True
            )
            self.view.import_steps.set_stage_enabled(1, allowed)
            self.view.import_steps.set_stage_enabled(
                2, allowed and self._selected_file is not None
            )
            self.view.import_steps.set_stage_enabled(3, False)
            self.view.import_steps.set_stage_enabled(4, False)

        self._run_operation(
            window_title="Importa\u00e7\u00e3o BOE",
            operation=operation,
            succeeded=succeeded,
            failed=failed,
            import_operation=True,
        )

    def refresh_history(self) -> None:
        try:
            self.view.show_history(self.service.list_imports())
        except (SQLAlchemyError, RuntimeError):
            self.service.repository.session.rollback()
            self.view.show_history([])
            self.view.set_status(
                "Histórico indisponível. Aplique as migrations do banco.",
                error=True,
            )

    def load_selected_details(self) -> None:
        import_id = self.view.selected_import_id()

        if import_id is None:
            self.view.clear_details()
            return

        def succeeded(details) -> None:
            if details is None:
                self.view.clear_details(
                    "A importa\u00e7\u00e3o selecionada "
                    "n\u00e3o foi encontrada."
                )
                return

            self.view.show_details(details)

        def failed(error: Exception) -> None:
            repository = getattr(
                self.service,
                "repository",
                None,
            )
            session = getattr(
                repository,
                "session",
                None,
            )

            if session is not None:
                try:
                    session.rollback()
                except Exception:
                    pass

            self.view.clear_details(
                "N\u00e3o foi poss\u00edvel carregar o detalhamento."
            )
            self.view.set_status(
                "Detalhamento BOE indispon\u00edvel.",
                error=True,
            )

        self._run_operation(
            window_title="Detalhamento BOE",
            operation=lambda: self.service.get_import_details(
                import_id
            ),
            succeeded=succeeded,
            failed=failed,
        )

    def refresh_operational_entities(self) -> None:
        if not hasattr(self.service, "list_operational_entities"):
            self.view.set_operational_entities(())
            return
        try:
            self.view.set_operational_entities(self.service.list_operational_entities())
        except (SQLAlchemyError, RuntimeError):
            self.view.set_operational_entities(())

    def query_operations(self) -> None:
        try:
            filters = self.view.operational_filters()
        except ValueError as error:
            self.view.set_status(str(error), error=True)
            return

        def succeeded(result) -> None:
            self.view.show_operations(result)
            self.view.set_status(
                "Consulta operacional BOE atualizada."
            )

        def failed(error: Exception) -> None:
            repository = getattr(
                self.service,
                "repository",
                None,
            )
            session = getattr(
                repository,
                "session",
                None,
            )

            if session is not None:
                try:
                    session.rollback()
                except Exception:
                    pass

            self.view.set_status(
                f"Falha ao consultar BOE: {error}",
                error=True,
            )

        self._run_operation(
            window_title="Consulta BOE",
            operation=lambda: self.service.query_operations(
                *filters
            ),
            succeeded=succeeded,
            failed=failed,
        )
