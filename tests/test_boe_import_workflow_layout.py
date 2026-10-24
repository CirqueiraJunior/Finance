import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path
from PySide6.QtWidgets import QApplication
from app.gui.pages.boe import BoePage
from app.importers.boe_types import (
    BOEIssueSeverity, BOEValidationIssue, BOEValidationResult,
)


def test_boe_workflow_and_issue_visibility():
    app = QApplication.instance() or QApplication([])
    page = BoePage()
    try:
        assert page.import_steps.STEPS == (
            "Selecionar", "Validar",
            "Comparar e autorizar", "Importar",
        )
        assert page.validation_issues.isHidden()
        assert page.validation_issues_label.isHidden()

        result = BOEValidationResult(
            Path("boe.xlsx"), "boe.xlsx"
        )
        result.inconsistencias.append(
            BOEValidationIssue(
                "Problema de teste", BOEIssueSeverity.ERROR,
                7, "ENTIDADE",
            )
        )
        page.show_validation(result)

        assert not page.validation_issues.isHidden()
        assert not page.validation_issues_label.isHidden()
        assert page.validation_issues.rowCount() == 1
        assert page.validation_issues.horizontalHeaderItem(2).text() == "C\u00f3digo"
        assert page.validation_issues.horizontalHeaderItem(3).text() == "Descri\u00e7\u00e3o"

        page.clear_validation_preview()
        assert page.validation_issues.isHidden()
        assert page.validation_issues.rowCount() == 0
    finally:
        page.close()
