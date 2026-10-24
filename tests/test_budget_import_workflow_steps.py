from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from app.gui.controllers.budget_controller import BudgetController
from app.gui.pages.orcamento import OrcamentoPage


class _BudgetWorkflowService:
    def __init__(self) -> None:
        self.validation_error = None
        self.validation_result = self.valid_validation()
        self.validated_paths = []
        self.import_calls = 0

    @staticmethod
    def valid_validation(*, can_import=True):
        return {
            "metadata": {
                "file_name": "orcamento.xlsx",
                "detected_type": "ORCAMENTO",
                "year": 2026,
            },
            "preview": [
                {
                    "line": 2,
                    "year": 2026,
                    "month": 1,
                    "entry_type": "RECEITA",
                    "category": "RECEITA_DIRETA",
                    "value": "200.0000",
                    "source_label": "Repasse",
                }
            ],
            "warnings": [],
            "errors": [] if can_import else ["Inconsistência bloqueante"],
            "can_import": can_import,
            "totals": {"rows": 1, "value": "200.0000"},
        }

    def available_years(self):
        return [2026]

    def validate_import(self, path):
        self.validated_paths.append(path)
        if self.validation_error is not None:
            raise self.validation_error
        return self.validation_result

    def import_file(self, _path):
        self.import_calls += 1
        return {"imported": 1, "year": 2026, "total": "200.0000"}


def _controller(qtbot):
    page = OrcamentoPage()
    qtbot.addWidget(page)
    service = _BudgetWorkflowService()
    controller = BudgetController(page, service, defer_initial_load=True)
    return page, controller, service


def _stage_states(page):
    return [button.isEnabled() for button in page.import_steps.buttons]


def _select_file(monkeypatch, page, path):
    monkeypatch.setattr(
        "app.gui.controllers.budget_controller.QFileDialog.getOpenFileName",
        lambda *_args: (path, "Planilhas Excel"),
    )
    page.import_steps.buttons[0].click()


def _authorize_stage(monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: next(
            button
            for button in self.buttons()
            if button.text() == "Autorizar etapa"
        ),
    )


def _cancel_stage(monkeypatch):
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: next(
            button for button in self.buttons() if button.text() == "Cancelar"
        ),
    )


def _advance_to_comparison(monkeypatch, page, file_path):
    summaries = []
    monkeypatch.setattr(
        QMessageBox,
        "information",
        lambda _parent, _title, message: summaries.append(message),
    )
    _select_file(monkeypatch, page, file_path)
    page.import_steps.buttons[1].click()
    page.import_steps.buttons[2].click()
    return summaries










def test_budget_import_result_uses_only_budget_contract_fields(qtbot):
    page = OrcamentoPage()
    qtbot.addWidget(page)

    page.show_import_result(
        {
            "imported": 3,
            "year": 2026,
            "total": "1234.5000",
            "updated": 99,
            "warnings": ["não deve aparecer"],
            "secret": "não deve aparecer",
        }
    )

    text = page.import_result.toPlainText()
    assert "3 registros" in text
    assert "Ano: 2026" in text
    assert "R$ 1.234,50" in text
    assert "updated" not in text
    assert "99" not in text
    assert "não deve aparecer" not in text
    assert page.import_result.isReadOnly()


def _comparison_validation(*, new=1, changed=0):
    result = _BudgetWorkflowService.valid_validation()
    rows = []
    if new:
        rows.append({
            "line": 2,
            "year": 2026,
            "month": 1,
            "entry_type": "RECEITA",
            "category": "RECEITA_DIRETA",
            "source_label": "Repasse",
            "status": "NEW",
            "previous_value": None,
            "value": "200.0000",
            "difference": "200.0000",
        })
    if changed:
        rows.append({
            "line": 3,
            "year": 2026,
            "month": 2,
            "entry_type": "DESPESA",
            "category": "PESSOAL",
            "source_label": "Salarios",
            "status": "CHANGED",
            "previous_value": "100.0000",
            "value": "150.0000",
            "difference": "50.0000",
        })
    if not rows:
        rows.append({
            "line": 2,
            "year": 2026,
            "month": 1,
            "entry_type": "RECEITA",
            "category": "RECEITA_DIRETA",
            "source_label": "Repasse",
            "status": "UNCHANGED",
            "previous_value": "200.0000",
            "value": "200.0000",
            "difference": "0.0000",
        })
    result["comparison_preview"] = rows
    result["comparison_totals"] = {
        "new": new, "changed": changed,
        "unchanged": 3, "invalid": 0,
    }
    return result


def _compare_budget(qtbot, monkeypatch, *, accepted, new=1, changed=0):
    from PySide6.QtWidgets import QDialog
    from app.gui.budget_comparison_dialog import BudgetComparisonDialog

    page, controller, service = _controller(qtbot)
    service.validation_result = _comparison_validation(
        new=new, changed=changed
    )
    seen = []

    def fake_exec(dialog):
        seen.append(dialog)
        return (
            QDialog.DialogCode.Accepted
            if accepted else QDialog.DialogCode.Rejected
        )

    monkeypatch.setattr(BudgetComparisonDialog, "exec", fake_exec)
    _select_file(monkeypatch, page, "C:/temp/orcamento.xlsx")
    page.import_steps.buttons[1].click()
    page.import_steps.buttons[2].click()
    return page, controller, service, seen


def test_budget_four_stages_authorization_and_final_confirmation(
    qtbot, monkeypatch,
):
    page, controller, service, seen = _compare_budget(
        qtbot, monkeypatch, accepted=True
    )
    assert len(page.import_steps.buttons) == 4
    assert page.import_steps.buttons[2].text() == "3. Comparar e autorizar"
    assert len(seen) == 1
    assert seen[0].authorize_button is not None
    assert (
        seen[0].authorize_button.text()
        == "Confirmar altera\u00e7\u00f5es"
    )
    assert page.import_steps.buttons[3].isEnabled()
    assert service.import_calls == 0

    imports = []
    monkeypatch.setattr(
        controller, "import_validated_file",
        lambda: imports.append(True),
    )
    monkeypatch.setattr(
        "app.gui.controllers.budget_controller.confirm_import",
        lambda *_args, **_kwargs: True,
    )
    page.import_steps.buttons[3].click()
    assert imports == [True]
    assert controller._workflow_authorized_file is None
    assert not page.import_steps.buttons[3].isEnabled()


def test_budget_comparison_cancel_blocks_import(qtbot, monkeypatch):
    page, controller, service, seen = _compare_budget(
        qtbot, monkeypatch, accepted=False
    )
    assert len(seen) == 1
    assert controller._workflow_authorized_file is None
    assert not page.import_steps.buttons[3].isEnabled()
    assert service.import_calls == 0


def test_budget_no_changes_block_authorization(qtbot, monkeypatch):
    page, controller, _, seen = _compare_budget(
        qtbot, monkeypatch, accepted=True, new=0, changed=0
    )
    assert seen[0].authorize_button is None
    assert controller._workflow_authorized_file is None
    assert not page.import_steps.buttons[3].isEnabled()


def test_budget_revalidation_revokes_authorization(qtbot, monkeypatch):
    page, controller, _, _ = _compare_budget(
        qtbot, monkeypatch, accepted=True
    )
    assert controller._workflow_authorized_file is not None
    page.import_steps.buttons[1].click()
    assert controller._workflow_authorized_file is None
    assert not page.import_steps.buttons[3].isEnabled()


def test_budget_dialog_real_unicode(qtbot, monkeypatch):
    page, controller, _, seen = _compare_budget(
        qtbot, monkeypatch, accepted=False
    )
    from PySide6.QtWidgets import QLabel
    dialog = seen[0]
    texts = " ".join(
        label.text() for label in dialog.findChildren(QLabel)
    )
    assert "Compara\u00e7\u00e3o" in texts
    assert "Sem altera\u00e7\u00e3o" in texts
    assert r"\u00e7" not in texts
    assert r"\u00e3" not in texts
    assert (
        dialog.table.horizontalHeaderItem(0).text()
        == "Situa\u00e7\u00e3o"
    )
