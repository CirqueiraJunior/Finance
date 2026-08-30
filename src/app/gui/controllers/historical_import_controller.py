from PySide6.QtCore import QObject

from app.gui.pages.historical_import import HistoricalImportDialog
from app.services.historical_import_service import HistoricalImportService


class HistoricalImportController(QObject):
    def __init__(self, dialog: HistoricalImportDialog,
                 service: HistoricalImportService) -> None:
        super().__init__(dialog)
        self.dialog, self.service = dialog, service
        self.preview = None
        dialog.analyze_button.clicked.connect(self.analyze)
        dialog.import_button.clicked.connect(self.import_data)

    def analyze(self) -> None:
        path = self.dialog.file_path.text()
        self.preview = self.service.analyze(
            path, self.dialog.requested_type.currentData()
        )
        self.dialog.show_preview(self.preview)

    def import_data(self) -> None:
        if self.preview is None:
            return
        try:
            report = self.service.import_preview(self.preview)
            self.dialog.show_report(report)
        except Exception as error:
            self.dialog.issues.setText(f"ERRO: importação revertida integralmente: {error}")
            self.dialog.import_button.setEnabled(False)
