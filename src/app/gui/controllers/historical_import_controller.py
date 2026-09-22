from PySide6.QtCore import QObject, QThread, Slot

from app.gui.processing import OperationWorker, ProcessingDialog
from app.gui.pages.historical_import import HistoricalImportDialog
from app.services.historical_import_service import HistoricalImportService


class HistoricalImportController(QObject):
    def __init__(self, dialog: HistoricalImportDialog,
                 service: HistoricalImportService) -> None:
        super().__init__(dialog)
        self.dialog, self.service = dialog, service
        self.preview = None
        self._import_thread: QThread | None = None
        self._import_worker: OperationWorker | None = None
        self._processing_dialog: ProcessingDialog | None = None
        dialog.analyze_button.clicked.connect(self.analyze)
        dialog.import_button.clicked.connect(self.import_data)

    def analyze(self) -> None:
        path = self.dialog.file_path.text()
        self.preview = self.service.analyze(
            path, self.dialog.requested_type.currentData()
        )
        self.dialog.show_preview(self.preview)

    def import_data(self) -> None:
        if self.preview is None or (
            self._import_thread is not None and self._import_thread.isRunning()
        ):
            return
        self.dialog.import_button.setEnabled(False)
        self.dialog.analyze_button.setEnabled(False)
        self.dialog.choose_button.setEnabled(False)
        self.dialog.cancel_button.setEnabled(False)
        self._processing_dialog = ProcessingDialog(
            self.dialog,
            window_title="Importação histórica",
            title="Importando dados...",
            description="Aguarde enquanto a solicitação é processada.",
        )
        self._processing_dialog.show()
        selected_preview = self.preview
        self._import_thread = QThread(self)
        self._import_worker = OperationWorker(
            lambda: self.service.import_preview(selected_preview)
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
    def _import_succeeded(self, report) -> None:
        self.dialog.show_report(report)
        self.preview = None

    @Slot(object)
    def _import_failed(self, error: Exception) -> None:
        self.dialog.issues.setText(
            f"ERRO: importação revertida integralmente: {error}"
        )
        self.preview = None

    @Slot()
    def _import_finished(self) -> None:
        if self._processing_dialog is not None:
            self._processing_dialog.accept()
            self._processing_dialog.deleteLater()
            self._processing_dialog = None
        if self._import_thread is not None:
            self._import_thread.deleteLater()
        self._import_thread = None
        self._import_worker = None
        self.dialog.choose_button.setEnabled(True)
        self.dialog.analyze_button.setEnabled(True)
        self.dialog.cancel_button.setEnabled(True)
        self.dialog.import_button.setEnabled(False)
