from types import SimpleNamespace

from finance_server.config import ServerSettings
from finance_server.environment import EnvironmentCommandError, ServerConnectionConfig
from finance_server import service_main, windows_service


def test_build_service_settings_uses_machine_store(monkeypatch):
    connection = ServerConnectionConfig(
        host="database.example", port=5432, database="postgres",
        username="finance.user", sslmode="require",
    )
    monkeypatch.setattr(
        service_main,
        "ServiceServerConfigStore",
        lambda: SimpleNamespace(load=lambda: (connection, "Password1", "K" * 48)),
    )
    monkeypatch.setattr(
        service_main, "build_postgres_url",
        lambda received, password: "postgresql+psycopg://protected"
        if (received, password) == (connection, "Password1") else "unexpected",
    )

    settings = service_main.build_service_settings()

    assert settings == ServerSettings(
        database_url="postgresql+psycopg://protected", secret_key="K" * 48
    )


def test_service_main_returns_controlled_code_when_configuration_is_missing(
    monkeypatch, capsys,
):
    monkeypatch.setattr(
        service_main, "build_service_settings",
        lambda: (_ for _ in ()).throw(EnvironmentCommandError("configuração ausente")),
    )

    assert service_main.run() == 2
    assert "configuração ausente" in capsys.readouterr().err


def test_windows_service_main_uses_scm_dispatcher_without_arguments(monkeypatch):
    calls = []
    monkeypatch.setattr(windows_service.sys, "argv", ["FinanceServer.exe"])
    monkeypatch.setattr(
        windows_service.servicemanager, "Initialize",
        lambda: calls.append("initialize"),
    )
    monkeypatch.setattr(
        windows_service.servicemanager, "PrepareToHostSingle",
        lambda cls: calls.append(("prepare", cls)),
    )
    monkeypatch.setattr(
        windows_service.servicemanager, "StartServiceCtrlDispatcher",
        lambda: calls.append("dispatch"),
    )

    windows_service.main()

    assert calls == [
        "initialize",
        ("prepare", windows_service.FinanceServerWindowsService),
        "dispatch",
    ]


def test_windows_service_main_keeps_command_line_management(monkeypatch):
    captured = []
    monkeypatch.setattr(
        windows_service.sys, "argv", ["FinanceServer.exe", "install"]
    )
    monkeypatch.setattr(
        windows_service.win32serviceutil, "HandleCommandLine",
        lambda cls: captured.append(cls),
    )

    windows_service.main()

    assert captured == [windows_service.FinanceServerWindowsService]


def test_service_stop_requests_graceful_uvicorn_exit(monkeypatch):
    service = object.__new__(windows_service.FinanceServerWindowsService)
    service.server = SimpleNamespace(should_exit=False)
    service.stop_event = object()
    service.stop_requested = False
    statuses = []
    service.ReportServiceStatus = statuses.append
    events = []
    monkeypatch.setattr(windows_service.win32event, "SetEvent", events.append)

    service.SvcStop()

    assert service.stop_requested is True
    assert service.server.should_exit is True
    assert statuses == [windows_service.win32service.SERVICE_STOP_PENDING]
    assert events == [service.stop_event]


def test_stop_requested_during_startup_prevents_server_from_staying_up(monkeypatch):
    service = object.__new__(windows_service.FinanceServerWindowsService)
    service.server = None
    service.stop_requested = True
    monkeypatch.setattr(windows_service, "create_service_app", lambda: object())
    monkeypatch.setattr(windows_service.uvicorn, "Config", lambda **kwargs: kwargs)
    created_servers = []

    class Server:
        def __init__(self, config):
            self.config = config
            self.should_exit = False
            self.ran = False
            created_servers.append(self)

        def run(self):
            self.ran = True

    monkeypatch.setattr(windows_service.uvicorn, "Server", Server)
    monkeypatch.setattr(windows_service.servicemanager, "LogInfoMsg", lambda _msg: None)

    service.SvcDoRun()

    assert len(created_servers) == 1
    assert created_servers[0].should_exit is True
    assert created_servers[0].ran is True
    assert service.server is None
