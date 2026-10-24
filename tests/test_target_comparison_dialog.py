from PySide6.QtWidgets import QLabel

from app.gui.target_comparison_dialog import TargetComparisonDialog


def _validation():
    return {
        "metadata": {"detected_type": "META_REALIZADO"},
        "can_import": True,
        "errors": [],
        "warnings": [],
        "totals": {"rows": 1},
        "preview": [{
            "line": 4,
            "entity_code": 7001,
            "entity_name": "Unidade A",
            "indicator": "META",
            "target": "200",
            "actual": "180",
        }],
    }


def test_target_preview_is_read_only(qtbot):
    dialog = TargetComparisonDialog(
        _validation(), can_authorize=True
    )
    qtbot.addWidget(dialog)
    assert dialog.preview_count == 1
    assert dialog.table.rowCount() == 1
    assert dialog.table.item(0, 1).text() == "Unidade A"
    assert dialog.authorize_button is not None


def test_target_cancel_does_not_authorize(qtbot):
    dialog = TargetComparisonDialog(
        _validation(), can_authorize=True
    )
    qtbot.addWidget(dialog)
    dialog.reject()
    assert dialog.result() == dialog.DialogCode.Rejected


def test_target_blocked_validation(qtbot):
    validation = _validation()
    validation["can_import"] = False
    dialog = TargetComparisonDialog(
        validation, can_authorize=True
    )
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is None


def test_target_no_preview_blocks_authorization(qtbot):
    validation = _validation()
    validation["preview"] = []
    validation["totals"]["rows"] = 0
    dialog = TargetComparisonDialog(
        validation, can_authorize=True
    )
    qtbot.addWidget(dialog)
    assert dialog.authorize_button is None


def test_target_accents_are_decoded(qtbot):
    dialog = TargetComparisonDialog(
        _validation(), can_authorize=True
    )
    qtbot.addWidget(dialog)
    texts = " ".join(
        widget.text()
        for widget in dialog.findChildren(QLabel)
    )
    assert "Pr\u00e9via" in texts
    assert "valida\u00e7\u00e3o" in texts
    assert r"\u00e7" not in texts


def test_target_association_uses_specific_columns(qtbot):
    validation = _validation()
    validation["metadata"]["detected_type"] = "ASSOCIACAO"
    validation["association_preview"] = [{
        "line": 5,
        "entity_name": "Unidade B",
        "association_name": "Associa\u00e7\u00e3o A",
        "value": "300",
    }]
    dialog = TargetComparisonDialog(
        validation, can_authorize=True
    )
    qtbot.addWidget(dialog)
    assert dialog.preview_count == 1
    assert (
        dialog.table.horizontalHeaderItem(2).text()
        == "Associa\u00e7\u00e3o"
    )
