import threading
from pathlib import Path

from PySide6.QtWidgets import QLabel

from app.gui.controllers.historical_import_controller import HistoricalImportController
from app.gui.pages.historical_import import HistoricalImportDialog
from app.gui.processing import ProcessingDialog
from app.importers.historical_importer import HistoricalPreview
from app.services.historical_import_service import ImportReport


class _HistoricalService:
    def __init__(self, *, error=None, wait=False):
        self.error = error
        self.wait = wait
        self.calls = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.worker_thread = None

    def import_preview(self, _preview):
        self.calls += 1
        self.worker_thread = threading.get_ident()
        self.started.set()
        if self.wait:
            self.release.wait(2)
        if self.error is not None:
            raise self.error
        return ImportReport(539, 539, 0, 0, 0, 0, "539", Path("backup.db"))


def _controller(qtbot, service):
    dialog = HistoricalImportDialog()
    qtbot.addWidget(dialog)
    controller = HistoricalImportController(dialog, service)
    controller.preview = HistoricalPreview(
        Path("associacao.xlsx"), "ASSOCIACAO", 2026, rows=[{"code": 7501}]
    )
    dialog.import_button.setEnabled(True)
    return dialog, controller


def test_historical_import_reuses_processing_dialog_and_blocks_duplicate(qtbot):
    service = _HistoricalService(wait=True)
    dialog, controller = _controller(qtbot, service)
    gui_thread = threading.get_ident()

    controller.import_data()
    qtbot.waitUntil(service.started.is_set)

    assert service.worker_thread != gui_thread
    assert service.calls == 1
    assert isinstance(controller._processing_dialog, ProcessingDialog)
    assert controller._processing_dialog.isVisible()
    texts = {
        label.text()
        for label in controller._processing_dialog.findChildren(QLabel)
    }
    assert "Importando dados..." in texts
    assert "Aguarde enquanto a solicitação é processada." in texts
    assert not dialog.import_button.isEnabled()

    controller.import_data()
    assert service.calls == 1

    with qtbot.waitSignal(controller._import_thread.finished, timeout=3000):
        service.release.set()

    assert controller._processing_dialog is None
    assert "Importação concluída. Processados: 539" in dialog.summary.text()
    assert not dialog.import_button.isEnabled()
    assert dialog.choose_button.isEnabled()
    assert dialog.analyze_button.isEnabled()
    assert dialog.cancel_button.isEnabled()


def test_historical_import_error_closes_processing_and_keeps_existing_message(qtbot):
    service = _HistoricalService(error=RuntimeError("falha simulada"), wait=True)
    dialog, controller = _controller(qtbot, service)

    controller.import_data()
    assert service.started.wait(1)
    with qtbot.waitSignal(controller._import_thread.finished, timeout=3000):
        service.release.set()

    assert controller._processing_dialog is None
    assert "ERRO: importação revertida integralmente: falha simulada" == dialog.issues.text()
    assert not dialog.import_button.isEnabled()
    assert dialog.choose_button.isEnabled()
    assert dialog.analyze_button.isEnabled()
    assert dialog.cancel_button.isEnabled()
