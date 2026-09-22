from __future__ import annotations

from PySide6.QtWidgets import QDialog, QMessageBox
from types import SimpleNamespace

from app.api_client.client import APIClient
from app.gui.initial_setup_dialog import InitialSetupDialog


class FakeClient:
    def __init__(self):
        self.created = []

    def create_initial_administrator(self, payload):
        self.created.append(payload)
        return {"id": 1}


def fill_valid(dialog):
    dialog.name.setText("Administrador")
    dialog.email.setText("admin@example.com")
    dialog.username.setText("admin")
    dialog.password.setText("Finance1")
    dialog.confirmation.setText("Finance1")


def test_setup_dialog_validates_confirmation_before_request(qtbot, monkeypatch):
    client = FakeClient()
    dialog = InitialSetupDialog(client)
    qtbot.addWidget(dialog)
    fill_valid(dialog)
    dialog.confirmation.setText("Finance2")
    messages = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args: messages.append(args[-1])
    )

    dialog._complete()

    assert client.created == []
    assert messages == ["A confirmação da senha não confere."]


def test_setup_dialog_creates_admin_and_returns_to_login_flow(qtbot, monkeypatch):
    client = FakeClient()
    dialog = InitialSetupDialog(client)
    qtbot.addWidget(dialog)
    fill_valid(dialog)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)

    dialog._complete()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert client.created == [{
        "nome": "Administrador",
        "email": "admin@example.com",
        "username": "admin",
        "password": "Finance1",
    }]


def test_api_client_uses_unauthenticated_setup_contract(monkeypatch):
    client = APIClient("http://127.0.0.1:8000")
    calls = []

    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        if method == "GET":
            return {"requires_initial_setup": True}
        return {"id": 1}

    monkeypatch.setattr(client, "_request", request)
    assert client.initial_setup_required() is True
    payload = {
        "nome": "Administrador",
        "email": "admin@example.com",
        "username": "admin",
        "password": "Finance1",
    }
    client.create_initial_administrator(payload)
    assert calls == [
        (
            "GET",
            "/api/v1/setup/status",
            {"authenticated": False},
        ),
        (
            "POST",
            "/api/v1/setup/administrator",
            {"authenticated": False, "json": payload},
        ),
    ]
    client.close()


def _prepare_main(monkeypatch, *, requires_setup, setup_result):
    import app.main as module

    events = []

    class Application:
        def processEvents(self):
            pass

    class Client:
        def __init__(self, *_args):
            events.append("client")

        def health(self):
            events.append("health")

        def initial_setup_required(self):
            events.append("status")
            return requires_setup

        def close(self):
            events.append("closed")

    class Setup:
        def __init__(self, _client):
            events.append("setup")

        def exec(self):
            events.append("setup-exec")
            return setup_result

    class Login:
        user = None

        def __init__(self, _client):
            events.append("login")

        def exec(self):
            events.append("login-exec")
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(module, "create_application", Application)
    monkeypatch.setattr(module, "show_splash", lambda _app: None)
    monkeypatch.setattr(module, "hold_splash", lambda _splash: None)
    monkeypatch.setattr(
        module,
        "get_settings",
        lambda: SimpleNamespace(api_url="http://127.0.0.1:8000", api_timeout_seconds=1),
    )
    monkeypatch.setattr(module, "APIClient", Client)
    monkeypatch.setattr(module, "InitialSetupDialog", Setup)
    monkeypatch.setattr(module, "LoginDialog", Login)
    return module, events


def test_startup_cancelled_setup_does_not_release_login_or_main_window(monkeypatch):
    module, events = _prepare_main(
        monkeypatch,
        requires_setup=True,
        setup_result=QDialog.DialogCode.Rejected,
    )
    monkeypatch.setattr(
        module,
        "MainWindow",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("MainWindow must not be opened")
        ),
    )

    assert module.main() == 0
    assert events == [
        "client", "health", "status", "setup", "setup-exec", "closed"
    ]


def test_startup_opens_login_after_successful_setup(monkeypatch):
    module, events = _prepare_main(
        monkeypatch,
        requires_setup=True,
        setup_result=QDialog.DialogCode.Accepted,
    )

    assert module.main() == 0
    assert events == [
        "client", "health", "status", "setup", "setup-exec",
        "login", "login-exec", "closed",
    ]


def test_startup_skips_setup_when_database_has_users(monkeypatch):
    module, events = _prepare_main(
        monkeypatch,
        requires_setup=False,
        setup_result=QDialog.DialogCode.Accepted,
    )

    assert module.main() == 0
    assert events == [
        "client", "health", "status", "login", "login-exec", "closed"
    ]
