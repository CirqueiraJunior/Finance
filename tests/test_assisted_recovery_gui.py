from app.gui.login_dialog import AssistedRecoveryDialog


class FakeClient:
    def __init__(self):
        self.completed = []

    def create_assisted_recovery_request(self, identifier):
        return {"message": "Solicitação processada.", "request_code": "request-code"}

    def validate_assisted_recovery(self, authorization):
        if authorization != "valid-authorization":
            raise RuntimeError("Autorização inválida.")

    def complete_assisted_recovery(self, authorization, password):
        self.completed.append((authorization, password))


def test_gui_does_not_allow_reset_before_valid_authorization(qtbot, monkeypatch):
    dialog = AssistedRecoveryDialog(FakeClient(), "active")
    qtbot.addWidget(dialog)
    assert not dialog.password.isEnabled()
    assert not dialog.confirmation.isEnabled()
    assert not dialog.reset_button.isEnabled()

    dialog.authorization.setPlainText("invalid")
    monkeypatch.setattr(
        "app.gui.login_dialog.QMessageBox.warning", lambda *args, **kwargs: None
    )
    dialog._validate_authorization()
    assert not dialog.reset_button.isEnabled()


def test_gui_request_validation_and_reset_flow(qtbot, monkeypatch):
    client = FakeClient()
    dialog = AssistedRecoveryDialog(client, "active")
    qtbot.addWidget(dialog)
    monkeypatch.setattr(
        "app.gui.login_dialog.QMessageBox.information", lambda *args, **kwargs: None
    )
    dialog._generate_request()
    assert dialog.request_code.toPlainText() == "request-code"
    assert dialog.copy_button.isEnabled()

    dialog.authorization.setPlainText("valid-authorization")
    dialog._validate_authorization()
    assert dialog.password.isEnabled()
    assert dialog.reset_button.isEnabled()
    dialog.password.setText("Finance2")
    dialog.confirmation.setText("Finance2")
    dialog._reset_password()
    assert client.completed == [("valid-authorization", "Finance2")]
