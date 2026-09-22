from PySide6.QtWidgets import QDialog, QMessageBox, QPushButton

from app.gui.login_dialog import (
    LoginDialog, PersonalRecoveryDialog, PersonalRecoveryKeyDialog,
)
from app.api_client.client import AuthenticatedUser


class FakeClient:
    def __init__(self):
        self.completed = []

    def complete_personal_recovery(self, identifier, recovery_key, password):
        self.completed.append((identifier, recovery_key, password))


def test_personal_key_dialog_is_read_only_and_copies(qtbot, monkeypatch):
    copied = []
    monkeypatch.setattr(
        "app.gui.login_dialog.QGuiApplication.clipboard",
        lambda: type("Clipboard", (), {"setText": lambda self, value: copied.append(value)})(),
    )
    dialog = PersonalRecoveryKeyDialog("FIN-one-time")
    qtbot.addWidget(dialog)
    assert dialog.key.isReadOnly()
    assert dialog.windowTitle() == "Chave pessoal de recuperação"
    dialog._copy()
    assert copied == ["FIN-one-time"]


def test_personal_recovery_gui_confirms_password_and_calls_api(qtbot, monkeypatch):
    client = FakeClient()
    dialog = PersonalRecoveryDialog(client, "usuario")
    qtbot.addWidget(dialog)
    messages = []
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))
    dialog.recovery_key.setText("FIN-secret-1")
    dialog.password.setText("Finance2")
    dialog.confirmation.setText("Finance2")
    dialog._reset()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert client.completed == [("usuario", "FIN-secret-1", "Finance2")]
    assert messages == ["Senha redefinida com sucesso."]


def test_personal_recovery_gui_rejects_mismatched_confirmation(qtbot, monkeypatch):
    client = FakeClient()
    dialog = PersonalRecoveryDialog(client, "usuario")
    qtbot.addWidget(dialog)
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[2]))
    dialog.recovery_key.setText("FIN-secret-1")
    dialog.password.setText("Finance2")
    dialog.confirmation.setText("Finance3")
    dialog._reset()
    assert client.completed == []
    assert warnings == ["As senhas informadas não coincidem."]


def test_personal_recovery_keeps_password_disabled_until_key_is_informed(qtbot):
    client = FakeClient()
    dialog = PersonalRecoveryDialog(client, "usuario")
    qtbot.addWidget(dialog)

    assert not dialog.password.isEnabled()
    assert not dialog.confirmation.isEnabled()
    assert not dialog.reset_button.isEnabled()

    dialog.recovery_key.setText("FIN-secret-1")

    assert dialog.password.isEnabled()
    assert dialog.confirmation.isEnabled()
    assert dialog.reset_button.isEnabled()


def test_login_exposes_only_one_recovery_entry_point(qtbot):
    dialog = LoginDialog(FakeClient())
    qtbot.addWidget(dialog)
    labels = [button.text() for button in dialog.findChildren(QPushButton)]
    assert labels.count("Esqueci minha senha") == 1
    assert "Recuperar com chave pessoal" not in labels
    assert "Recuperação assistida" not in labels


def test_forgot_opens_personal_recovery_with_current_identifier(qtbot, monkeypatch):
    opened = []

    class Recovery:
        def __init__(self, client, identifier, parent):
            opened.append((client, identifier, parent))

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("app.gui.login_dialog.PersonalRecoveryDialog", Recovery)
    client = FakeClient()
    dialog = LoginDialog(client)
    qtbot.addWidget(dialog)
    dialog.identifier.setText("usuario@example.com")
    dialog._forgot()
    assert opened == [(client, "usuario@example.com", dialog)]


def test_personal_recovery_opens_existing_assisted_flow(qtbot, monkeypatch):
    opened = []

    class Assisted:
        def __init__(self, client, identifier, parent):
            opened.append((client, identifier, parent))

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("app.gui.login_dialog.AssistedRecoveryDialog", Assisted)
    client = FakeClient()
    dialog = PersonalRecoveryDialog(client, "usuario")
    qtbot.addWidget(dialog)
    assert dialog.windowTitle() == "Finance — Recuperar senha"
    assert dialog.assisted_button.text() == "Não tenho a chave — Recuperação assistida"
    dialog._open_assisted_recovery()
    assert opened == [(client, "usuario", dialog)]


def test_login_shows_pending_personal_key_only_when_returned(qtbot, monkeypatch):
    shown = []

    class Client:
        pending = True

        def login(self, identifier, password):
            return AuthenticatedUser(
                9, "Usuário", "CONSULTA", False,
                "FIN-pending-once" if self.pending else None,
            )

    class KeyDialog:
        def __init__(self, key, parent):
            shown.append((key, parent))

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr("app.gui.login_dialog.PersonalRecoveryKeyDialog", KeyDialog)
    client = Client()
    first = LoginDialog(client)
    qtbot.addWidget(first)
    first._login()
    assert first.result() == QDialog.DialogCode.Accepted
    assert shown == [("FIN-pending-once", first)]

    client.pending = False
    second = LoginDialog(client)
    qtbot.addWidget(second)
    second._login()
    assert second.result() == QDialog.DialogCode.Accepted
    assert len(shown) == 1
