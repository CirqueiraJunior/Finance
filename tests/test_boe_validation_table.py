import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from app.gui.pages.boe import BoePage
from app.importers.boe_types import (
    BOEIssueSeverity, BOEValidationIssue, BOEValidationResult,
)


def test_issues_are_ordered_and_visible():
    app = QApplication.instance() or QApplication([])
    page = BoePage()
    try:
        result = BOEValidationResult(
            caminho_arquivo=Path("teste.xlsx"),
            nome_arquivo="teste.xlsx",
        )
        result.inconsistencias.extend([
            BOEValidationIssue(
                "Aviso de conferencia",
                BOEIssueSeverity.WARNING, 28, "A01",
            ),
            BOEValidationIssue(
                "Valor invalido",
                BOEIssueSeverity.ERROR, 15, "E01",
            ),
        ])
        page.show_validation(result)
        table = page.validation_issues
        assert table.rowCount() == 2
        assert table.item(0, 0).text() == "Erro"
        assert table.item(0, 1).text() == "15"
        assert table.item(0, 2).text() == "E01"
        assert table.item(1, 0).text() == "Aviso"
        assert result.aprovado is False
    finally:
        page.close()


def test_clean_validation_clears_issue_rows():
    app = QApplication.instance() or QApplication([])
    page = BoePage()
    try:
        invalid = BOEValidationResult(Path("x.xlsx"), "x.xlsx")
        invalid.inconsistencias.append(
            BOEValidationIssue(
                "Erro", BOEIssueSeverity.ERROR, 3
            )
        )
        page.show_validation(invalid)
        assert page.validation_issues.rowCount() == 1

        clean = BOEValidationResult(Path("y.xlsx"), "y.xlsx")
        page.show_validation(clean)
        assert page.validation_issues.rowCount() == 0
    finally:
        page.close()
