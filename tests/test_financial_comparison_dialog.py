from PySide6.QtWidgets import QDialog

from app.gui.financial_comparison_dialog import FinancialComparisonDialog


def validation():
    return {
        "can_import": True,
        "warnings": [],
        "errors": [],
        "preview": [
            {
                "line": 2, "year": 2026, "month": 1,
                "type": "RECEITA", "description": "Repasse",
                "category": "RECEITA_DIRETA", "value": "100",
            },
            {"line": 3, "duplicate": True},
            {"line": 4, "skip": True},
        ],
    }


def test_financial_classification(qtbot):
    dialog = FinancialComparisonDialog(
        validation(), can_authorize=True
    )
    qtbot.addWidget(dialog)
    assert dialog.eligible_count == 1
    assert dialog.duplicate_count == 1
    assert dialog.skipped_count == 1
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 3).text() == "Repasse"
    assert dialog.authorize_button is not None


def test_no_eligible_rows(qtbot):
    data = validation()
    data["preview"] = [
        {"duplicate": True},
        {"skip": True},
    ]
    dialog = FinancialComparisonDialog(
        data, can_authorize=True
    )
    qtbot.addWidget(dialog)
    assert dialog.eligible_count == 0
    assert dialog.authorize_button is None


def test_validation_errors_block(qtbot):
    data = validation()
    data["errors"] = ["Categoria inválida"]
    dialog = FinancialComparisonDialog(
        data, can_authorize=True
    )
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is None


def test_can_import_false_blocks(qtbot):
    data = validation()
    data["can_import"] = False
    dialog = FinancialComparisonDialog(
        data, can_authorize=True
    )
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is None


def test_cancel_and_explicit_accept(qtbot):
    dialog = FinancialComparisonDialog(
        validation(), can_authorize=True
    )
    qtbot.addWidget(dialog)
    dialog.reject()
    assert dialog.result() == QDialog.DialogCode.Rejected

    another = FinancialComparisonDialog(
        validation(), can_authorize=True
    )
    qtbot.addWidget(another)
    another.authorize_button.click()
    assert another.result() == QDialog.DialogCode.Accepted


def test_correct_accents(qtbot):
    dialog = FinancialComparisonDialog(
        validation(), can_authorize=True
    )
    qtbot.addWidget(dialog)
    assert "Prévia" in dialog.windowTitle()
    assert (
        dialog.table.horizontalHeaderItem(3).text()
        == "Descrição"
    )
