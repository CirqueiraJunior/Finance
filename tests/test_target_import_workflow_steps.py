
from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from app.gui.controllers.target_controller import TargetController
from app.gui.pages.metas import MetasPage


class FakeService:
    def available_years(self):
        return [2026]

    def validate_import(self, path):
        return {
            "metadata": {
                "file_name": Path(path).name,
                "detected_type": "META_REALIZADO",
                "year": 2026,
            },
            "totals": {"rows": 1, "target": "100", "actual": "80"},
            "preview": [{
                "line": 1,
                "entity_code": 7001,
                "entity_name": "Unidade A",
                "indicator": "CONSULTAS",
                "target": "100",
                "actual": "80",
            }],
            "warnings": [],
            "errors": [],
            "can_import": True,
        }

    def import_file(self, path):
        raise AssertionError("Importacao real proibida")


def build(qtbot):
    page = MetasPage()
    qtbot.addWidget(page)
    controller = TargetController(
        page, FakeService(), defer_initial_load=True
    )
    return page, controller


def test_four_stages_and_single_use(qtbot, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from app.gui.target_comparison_dialog import TargetComparisonDialog

    page, controller = build(qtbot)
    calls = []
    controller.import_validated_file = lambda: calls.append("import")

    monkeypatch.setattr(
        "app.gui.controllers.target_controller.QFileDialog.getOpenFileName",
        lambda *_args: ("metas.xlsx", "Excel"),
    )
    monkeypatch.setattr(
        TargetComparisonDialog,
        "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )

    assert len(page.import_steps.buttons) == 4
    controller.import_workflow_step()
    assert calls == []

    page.import_steps.buttons[0].click()
    assert page.import_steps.buttons[1].isEnabled()

    page.import_steps.buttons[1].click()
    assert page.import_steps.buttons[2].isEnabled()
    assert not page.import_steps.buttons[3].isEnabled()

    page.import_steps.buttons[2].click()
    assert page.import_steps.buttons[3].isEnabled()
    assert controller._workflow_authorized_file == "metas.xlsx"
    assert calls == []

    page.import_steps.buttons[3].click()
    assert calls == ["import"]
    assert controller._workflow_authorized_file is None
    assert not page.import_steps.buttons[3].isEnabled()

    controller.import_workflow_step()
    assert calls == ["import"]




def test_revalidation_revokes_authorization(qtbot):
    page, controller = build(qtbot)
    controller.selected_import_file_path = "metas.xlsx"
    controller.validate_import_file("metas.xlsx")
    controller._workflow_compared = True
    controller._workflow_authorized_file = "metas.xlsx"
    controller.validate_import_file("metas.xlsx")

    assert controller._workflow_authorized_file is None
    assert not page.import_steps.buttons[3].isEnabled()


def test_stale_validation_is_ignored(qtbot, monkeypatch):
    page, controller = build(qtbot)
    callbacks = []

    monkeypatch.setattr(
        controller, "_run_operation",
        lambda **kwargs: callbacks.append(kwargs["succeeded"]),
    )

    controller.selected_import_file_path = "a.xlsx"
    controller.validate_import_file("a.xlsx")
    controller.selected_import_file_path = "b.xlsx"
    controller.validate_import_file("b.xlsx")

    callbacks[0](controller.service.validate_import("a.xlsx"))
    assert controller._last_import_validation is None

    callbacks[1](controller.service.validate_import("b.xlsx"))
    assert controller._last_import_validation_path == "b.xlsx"
    assert page.import_steps.buttons[2].isEnabled()


def test_result_panel_uses_metas_fields(qtbot):
    page = MetasPage()
    qtbot.addWidget(page)
    page.show_import_result({
        "imported": 3,
        "year": 2026,
        "target_total": "1200",
        "actual_total": "900",
    })

    result = page.import_result.toPlainText()
    assert "3" in result
    assert "2026" in result
    assert "900" in result
