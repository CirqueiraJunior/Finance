from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QDialog
from app.gui.controllers.boe_controller import BOEController
from app.gui.pages.boe import BoePage


def context(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    controller = BOEController(
        page, object(), defer_initial_load=True
    )
    preview = SimpleNamespace(
        aprovado=True,
        caminho_arquivo=Path("boe.xlsx"),
        nome_arquivo="boe.xlsx",
        periodo_ano=2026,
        periodo_mes=10,
        quantidade_erros=0,
        quantidade_avisos=0,
        linhas=(),
        inconsistencias=(),
    )
    controller._selected_file = Path("boe.xlsx")
    controller._last_boe_preview = preview
    controller._validated_boe = preview
    return page, controller


def test_cancel_does_not_authorize(qtbot, monkeypatch):
    page, controller = context(qtbot)
    monkeypatch.setattr(
        "app.gui.boe_comparison_dialog.BOEComparisonDialog.exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    controller.compare_file()
    assert not controller._boe_step_confirmed
    assert not page.import_steps.buttons[3].isEnabled()


def test_accept_authorizes(qtbot, monkeypatch):
    page, controller = context(qtbot)
    monkeypatch.setattr(
        "app.gui.boe_comparison_dialog.BOEComparisonDialog.exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    controller.compare_file()
    assert controller._boe_step_confirmed
    assert page.import_steps.buttons[3].isEnabled()


def test_changed_file_blocks_authorization(qtbot, monkeypatch):
    page, controller = context(qtbot)
    controller._selected_file = Path("outro.xlsx")
    monkeypatch.setattr(
        "app.gui.boe_comparison_dialog.BOEComparisonDialog.exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    controller.compare_file()
    assert not controller._boe_step_confirmed
    assert not page.import_steps.buttons[3].isEnabled()
