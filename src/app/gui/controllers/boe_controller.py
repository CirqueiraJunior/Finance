from pathlib import Path

from PySide6.QtCore import QObject, QThread, Slot
from PySide6.QtWidgets import QFileDialog
from sqlalchemy.exc import SQLAlchemyError

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
        self.view.select_button.clicked.connect(self.select_file)
        self.view.validate_button.clicked.connect(self.validate_file)
        self.view.import_button.clicked.connect(self.import_file)
        self.view.history_table.itemSelectionChanged.connect(
            self.load_selected_details
        )
        self.view.query_button.clicked.connect(self.query_operations)
        self.refresh_history()
        self.refresh_operational_entities()

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
        try:
            result = self.service.validate_file(self._selected_file)
        except Exception as error:  # defensive GUI boundary
            self.view.import_button.setEnabled(False)
            self.view.set_status(f"Falha ao validar: {error}", error=True)
            return
        self.view.show_validation(result)
        self.view.import_button.setEnabled(result.aprovado)
        self.view.set_status(
            "Validação aprovada. O arquivo está pronto para importação."
            if result.aprovado
            else "Validação reprovada. Corrija os erros impeditivos.",
            error=not result.aprovado,
        )

    def import_file(self) -> None:
        if self._selected_file is None or (
            self._import_thread is not None and self._import_thread.isRunning()
        ):
            return
        self.view.import_button.setEnabled(False)
        self.view.select_button.setEnabled(False)
        self.view.validate_button.setEnabled(False)
        self._import_dialog = ProcessingDialog(
            self.view, window_title="Importação BOE"
        )
        self._import_dialog.show()
        selected_file = self._selected_file
        self._import_thread = QThread(self)
        self._import_worker = OperationWorker(
            lambda: self.service.import_file(selected_file)
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
    def _import_succeeded(self, imported: object) -> None:
        self.view.show_import_success(imported)
        self.view.set_status(
            f"BOE {imported.periodo_mes:02d}/{imported.periodo_ano} importado com sucesso."
        )
        self.refresh_history()
        self.refresh_operational_entities()

    @Slot(object)
    def _import_failed(self, error: Exception) -> None:
        if isinstance(error, BOEValidationError):
            self.view.show_validation(error.result)
            self.view.show_import_error(str(error))
            self.view.set_status(str(error), error=True)
            return
        if isinstance(error, BOEDomainError):
            self.view.show_import_error(str(error))
            self.view.set_status(str(error), error=True)
            return
        self.view.show_import_error(str(error))
        self.view.set_status(f"Falha ao importar: {error}", error=True)

    @Slot()
    def _import_finished(self) -> None:
        if self._import_dialog is not None:
            self._import_dialog.accept()
            self._import_dialog.deleteLater()
        if self._import_thread is not None:
            self._import_thread.deleteLater()
        self._import_dialog = None
        self._import_thread = None
        self._import_worker = None
        self.view.select_button.setEnabled(True)
        self.view.validate_button.setEnabled(self._selected_file is not None)
        # A completed attempt must be validated again before another import.
        self.view.import_button.setEnabled(False)

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
        try:
            details = self.service.get_import_details(import_id)
        except (SQLAlchemyError, RuntimeError):
            self.service.repository.session.rollback()
            self.view.clear_details("Não foi possível carregar o detalhamento.")
            self.view.set_status("Detalhamento BOE indisponível.", error=True)
            return
        if details is None:
            self.view.clear_details("A importação selecionada não foi encontrada.")
            return
        self.view.show_details(details)

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
            self.view.show_operations(
                self.service.query_operations(*self.view.operational_filters())
            )
            self.view.set_status("Consulta operacional BOE atualizada.")
        except (ValueError, SQLAlchemyError, RuntimeError) as error:
            self.view.set_status(f"Falha ao consultar BOE: {error}", error=True)
