import os

from PySide6.QtCore import QObject

from app.gui.pages.administracao import AdministracaoPage
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
        try:
            path = self.backup.create_manual_backup()
            self.view.set_status(f"Backup concluído: {path}")
        except (OSError, ValueError) as error:
            self.view.set_status(f"Falha no backup: {error}", error=True)

    def open_historical_import(self) -> None:
        if self.historical is None:
            self.view.set_status("Serviço de importação indisponível.", error=True)
            return
        dialog = HistoricalImportDialog(self.view)
        dialog.controller = HistoricalImportController(dialog, self.historical)
        dialog.exec()
        self.refresh()
