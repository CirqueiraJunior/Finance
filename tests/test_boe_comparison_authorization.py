"""Contratos de seguranca para a comparacao compartilhada BOE."""

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QDialog

from app.gui.boe_comparison_dialog import BOEComparisonDialog


def preview(*, approved=True, path="boe.xlsx"):
    return SimpleNamespace(
        aprovado=approved,
        caminho_arquivo=Path(path),
        nome_arquivo=Path(path).name,
        periodo_ano=2026,
        periodo_mes=10,
        quantidade_erros=0 if approved else 1,
        quantidade_avisos=0,
        linhas=(object(),),
        inconsistencias=(),
    )


def test_dialog_cancel_does_not_accept(qtbot):
    dialog = BOEComparisonDialog(preview())
    qtbot.addWidget(dialog)
    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected


def test_rejected_validation_never_shows_authorization(qtbot):
    dialog = BOEComparisonDialog(preview(approved=False))
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is None


def test_readonly_comparison_has_no_database_service(qtbot):
    dialog = BOEComparisonDialog(preview())
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is not None
    assert not hasattr(dialog, "service")


def test_explicit_permission_is_required(qtbot):
    dialog = BOEComparisonDialog(
        preview(), can_authorize=False
    )
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is None
