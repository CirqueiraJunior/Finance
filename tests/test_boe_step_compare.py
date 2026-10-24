from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QDialog
from app.gui.controllers.boe_controller import BOEController
from app.gui.pages.boe import BoePage


def test_compare_requires_validation(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    controller = BOEController(
        page, object(), defer_initial_load=True
    )
    controller.compare_file()
    assert not controller._boe_step_confirmed
    assert not page.import_steps.buttons[3].isEnabled()


def test_rejected_preview_cannot_authorize(qtbot, monkeypatch):
    page = BoePage()
    qtbot.addWidget(page)
    controller = BOEController(
        page, object(), defer_initial_load=True
    )
    controller._selected_file = Path("boe.xlsx")
    controller._last_boe_preview = SimpleNamespace(
        aprovado=False,
        caminho_arquivo=Path("boe.xlsx"),
        periodo_ano=2026,
        periodo_mes=10,
        nome_arquivo="boe.xlsx",
        quantidade_erros=1,
        quantidade_avisos=0,
        linhas=(),
        inconsistencias=(),
    )
    monkeypatch.setattr(
        "app.gui.boe_comparison_dialog.BOEComparisonDialog.exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    controller.compare_file()
    assert not controller._boe_step_confirmed
    assert not page.import_steps.buttons[3].isEnabled()
