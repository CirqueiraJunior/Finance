from types import SimpleNamespace

from PySide6.QtWidgets import QDialog, QWidget

from app.gui.controllers.cashflow_controller import CashflowController


def context(qtbot):
    page = QWidget()
    qtbot.addWidget(page)
    stages = {}
    messages = []
    page.import_steps = SimpleNamespace(
        set_stage_enabled=lambda stage, value:
            stages.__setitem__(stage, bool(value))
    )
    page.set_status = lambda text, **kw: messages.append(text)

    validation = {"can_import": True, "preview": [{
        "line": 2,
        "year": 2026,
        "month": 1,
        "description": "Repasse",
        "value": "100",
    }]}

    obj = SimpleNamespace(
        view=page,
        import_file_path="financeiro.xlsx",
        _last_import_validation=validation,
        _import_validated=True,
        _import_compared=False,
        _import_step_confirmed=False,
        _authorized_import_file=None,
        _validation_generation=1,
    )
    return obj, stages, messages


def install_dialog(monkeypatch, decision):
    seen = []

    class FakeDialog:
        def __init__(self, validation, **kwargs):
            seen.append(validation)
            self.authorize_button = object()

        def exec(self):
            return decision

    monkeypatch.setattr(
        "app.gui.financial_comparison_dialog.FinancialComparisonDialog",
        FakeDialog,
    )
    return seen


def test_comparison_cancel_does_not_authorize(qtbot, monkeypatch):
    obj, stages, _ = context(qtbot)
    install_dialog(monkeypatch, QDialog.DialogCode.Rejected)

    CashflowController.compare_import_file(obj)

    assert obj._authorized_import_file is None
    assert obj._import_step_confirmed is False
    assert stages[4] is False


def test_comparison_authorizes_without_importing(qtbot, monkeypatch):
    obj, stages, _ = context(qtbot)
    seen = install_dialog(monkeypatch, QDialog.DialogCode.Accepted)

    CashflowController.compare_import_file(obj)

    assert len(seen) == 1
    assert obj._authorized_import_file == "financeiro.xlsx"
    assert obj._import_step_confirmed is True
    assert stages[4] is True


def test_comparison_requires_valid_validation(qtbot, monkeypatch):
    obj, stages, _ = context(qtbot)
    obj._import_validated = False
    seen = install_dialog(monkeypatch, QDialog.DialogCode.Accepted)

    CashflowController.compare_import_file(obj)

    assert seen == []
    assert obj._authorized_import_file is None
    assert obj._import_step_confirmed is False
    assert stages[4] is False
