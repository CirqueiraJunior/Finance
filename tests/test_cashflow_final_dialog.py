from types import SimpleNamespace
from PySide6.QtWidgets import QMessageBox, QWidget
from app.gui.controllers.cashflow_controller import CashflowController


def test_final_dialog_cancel_is_false(qtbot, monkeypatch):
    view = QWidget()
    qtbot.addWidget(view)
    ctx = SimpleNamespace(view=view, import_file_path="teste.xlsx")
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox, "clickedButton", lambda self: None
    )
    assert not CashflowController._request_final_import_confirmation(ctx)


def test_final_dialog_explicit_accept_is_true(qtbot, monkeypatch):
    view = QWidget()
    qtbot.addWidget(view)
    ctx = SimpleNamespace(view=view, import_file_path="teste.xlsx")
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox, "clickedButton",
        lambda self: next(
            b for b in self.buttons()
            if b.text().startswith("Confirmar")
        ),
    )
    assert CashflowController._request_final_import_confirmation(ctx)


def test_final_dialog_without_file_is_false(qtbot):
    view = QWidget()
    qtbot.addWidget(view)
    ctx = SimpleNamespace(view=view, import_file_path=None)
    assert not CashflowController._request_final_import_confirmation(ctx)
