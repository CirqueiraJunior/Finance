from pathlib import Path

from PySide6.QtCore import QObject, QThread
from PySide6.QtWidgets import QFileDialog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import BOEDomainError, BOEValidationError
from app.gui.pages.boe import BoePage
from app.gui.processing import OperationWorker, ProcessingDialog
from app.services.boe_service import BOEService


class BOEController(QObject):
    def __init__(self, view: BoePage, service: BOEService) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self._selected_file: Path | None = None
        self._import_thread: QThread | None = None
        self._import_worker: OperationWorker | None = None
        self._import_dialog: ProcessingDialog | None = None
        self._operation_thread: QThread | None = None
        self._operation_worker: OperationWorker | None = None
        self._operation_dialog: ProcessingDialog | None = None
        self.view.select_button.clicked.connect(self.select_file)
        self.view.validate_button.clicked.connect(self.validate_file)
        self.view.import_button.clicked.connect(self.import_file)
        self.view.history_table.itemSelectionChanged.connect(
            self.load_selected_details
        )
        self.view.query_button.clicked.connect(self.query_operations)
        self.refresh_history()
        self.refresh_operational_entities()

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
        selected, _ = QFileDialog.getOpenFileName(
            self.view,
            "Selecionar arquivo BOE",
            "",
            "Planilhas Excel (*.xlsx)",
        )
        if not selected:
            return
        self._selected_file = Path(selected)
        self.view.file_path.setText(selected)
        self.view.validate_button.setEnabled(True)
        self.view.import_button.setEnabled(False)
        self.view.validation_result.clear()
        self.view.clear_import_result()
        self.view.set_status("Arquivo selecionado. Execute a validação.")

    def validate_file(self) -> None:
        if self._selected_file is None:
            return

        selected_file = self._selected_file
        self.view.import_button.setEnabled(False)

        def succeeded(result) -> None:
            self.view.show_validation(result)
            self.view.import_button.setEnabled(result.aprovado)
            self.view.set_status(
                (
                    "Valida\u00e7\u00e3o aprovada. "
                    "O arquivo est\u00e1 pronto para importa\u00e7\u00e3o."
                )
                if result.aprovado
                else (
                    "Valida\u00e7\u00e3o reprovada. "
                    "Corrija os erros impeditivos."
                ),
                error=not result.aprovado,
            )

        def failed(error: Exception) -> None:
            self.view.import_button.setEnabled(False)
            self.view.set_status(
                f"Falha ao validar: {error}",
                error=True,
            )

        self._run_operation(
            window_title="Valida\u00e7\u00e3o BOE",
            operation=lambda: self.service.validate_file(
                selected_file
            ),
            succeeded=succeeded,
            failed=failed,
        )

    def import_file(self) -> None:
        if self._selected_file is None:
            return

        selected_file = self._selected_file

        self.view.import_button.setEnabled(False)
        self.view.select_button.setEnabled(False)
        self.view.validate_button.setEnabled(False)

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

            self.view.select_button.setEnabled(True)
            self.view.validate_button.setEnabled(True)

            # Toda nova tentativa exige nova validacao.
            self.view.import_button.setEnabled(False)

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

            self.view.select_button.setEnabled(True)
            self.view.validate_button.setEnabled(
                self._selected_file is not None
            )
            self.view.import_button.setEnabled(False)

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
        filters = self.view.operational_filters()

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
