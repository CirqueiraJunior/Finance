"""Testes da apresentação de inconsistências no comparador BOE."""

from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QDialog

from app.gui.boe_comparison_dialog import BOEComparisonDialog


def test_compare_avoids_repeating_validation_issues(qtbot):
    result = SimpleNamespace(
        aprovado=False,
        caminho_arquivo=Path("BOE - 09.26.xlsx"),
        nome_arquivo="BOE - 09.26.xlsx",
        periodo_ano=2026,
        periodo_mes=9,
        quantidade_erros=2,
        quantidade_avisos=1,
        linhas=(),
        inconsistencias=[
            SimpleNamespace(
                severidade=SimpleNamespace(value="ERROR"),
                linha=12,
                codigo="PERIODO",
                mensagem="Competencia ja importada",
            ),
            SimpleNamespace(
                severidade=SimpleNamespace(value="WARNING"),
                linha=23,
                codigo="7600",
                mensagem="Verificar lancamento",
            ),
        ],
    )

    dialog = BOEComparisonDialog(
        result,
        can_authorize=False,
    )
    qtbot.addWidget(dialog)

    table = dialog.table
    contents = [
        table.item(row, column).text()
        for row in range(table.rowCount())
        for column in range(table.columnCount())
        if table.item(row, column) is not None
    ]

    text = " ".join(contents)

    assert "Competencia ja importada" in text
    assert "Verificar lancamento" in text
    assert "PERIODO" in text
    assert "7600" in text

    assert dialog.authorize_button is None

    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected
