import os

from PySide6.QtCore import QObject, QThread

from app.gui.pages.administracao import AdministracaoPage
from app.gui.processing import OperationWorker, ProcessingDialog
from app.gui.pages.historical_import import HistoricalImportDialog
from app.services.administration_service import AdministrationService
from app.services.backup_service import BackupService
from app.services.historical_import_service import HistoricalImportService
from app.gui.controllers.historical_import_controller import HistoricalImportController


class AdministrationController(QObject):
    def __init__(self, view: AdministracaoPage, service: AdministrationService,
                 backup: BackupService,
                 historical: HistoricalImportService | None = None) -> None:
        super().__init__(view)
        self.view, self.service, self.backup = view, service, backup
        self.historical = historical
        self._backup_thread: QThread | None = None
        self._backup_worker: OperationWorker | None = None
        self._backup_dialog: ProcessingDialog | None = None
        view.refresh_button.clicked.connect(self.refresh)
        view.logs_button.clicked.connect(self.open_logs)
        view.backup_button.clicked.connect(self.create_backup)
        view.import_button.clicked.connect(self.open_historical_import)
        self.refresh()

    def refresh(self) -> None:
        try:
            self.view.show_information(self.service.information())
            self.view.set_status("Informações atualizadas.")
        except Exception as error:
            self.view.set_status(f"Falha ao consultar informações: {error}", error=True)

    def open_logs(self) -> None:
        directory = self.service.settings.log_dir
        directory.mkdir(parents=True, exist_ok=True)
        os.startfile(directory)

    def create_backup(self) -> None:
        if (
            self._backup_thread is not None
            and self._backup_thread.isRunning()
        ):
            return

        dialog = ProcessingDialog(
            self.view,
            window_title="Criando Backup",
        )
        thread = QThread(self)
        worker = OperationWorker(
            self.backup.create_manual_backup
        )
        worker.moveToThread(thread)

        self._backup_dialog = dialog
        self._backup_thread = thread
        self._backup_worker = worker

        state = {
            "ok": False,
            "result": None,
            "error": None,
        }

        def succeeded(path) -> None:
            state["ok"] = True
            state["result"] = path

        def failed(error: Exception) -> None:
            state["error"] = error

        def finished() -> None:
            if self._backup_dialog is not None:
                self._backup_dialog.accept()
                self._backup_dialog.deleteLater()

            if self._backup_thread is not None:
                self._backup_thread.deleteLater()

            self._backup_dialog = None
            self._backup_thread = None
            self._backup_worker = None

            if state["ok"]:
                self.view.set_status(
                    f"Backup conclu\u00eddo: {state['result']}"
                )
            else:
                self.view.set_status(
                    f"Falha no backup: {state['error']}",
                    error=True,
                )

        thread.started.connect(worker.run)
        worker.succeeded.connect(succeeded)
        worker.failed.connect(failed)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(finished)

        dialog.show()
        thread.start()

    def open_historical_import(self) -> None:
        if self.historical is None:
            self.view.set_status("Serviço de importação indisponível.", error=True)
            return
        dialog = HistoricalImportDialog(self.view)
        dialog.controller = HistoricalImportController(dialog, self.historical)
        dialog.exec()
        self.refresh()
