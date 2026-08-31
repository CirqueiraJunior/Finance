import json
import os
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.core.config import get_settings
from app.database.alembic_config import set_alembic_database_url
from finance_server.config import get_server_settings
from finance_server.environment import (
    EnvironmentCommandError, PortProcess, SecureServerConfigStore,
    ServerConnectionConfig, assert_safe_finance_processes,
    build_postgres_url, dev_database_path, dev_environment,
    is_finance_api_process, parse_port_processes, protect_for_current_user,
    process_exists, stop_process, unprotect_for_current_user,
)
from finance_server import environment_cli


def _finance_process(pid=123) -> PortProcess:
    return PortProcess(
        pid, "python.exe", r"C:\venv\Scripts\python.exe",
        "python -m uvicorn finance_server.app_factory:create_app "
        "--factory --host 127.0.0.1 --port 8000",
    )


def test_dev_environment_uses_isolated_sqlite_without_postgresql(tmp_path):
    environment = dev_environment(tmp_path)

    expected = (tmp_path / "J.A. Technology" / "Finance" / "dev" / "finance_dev.db").resolve()
    assert environment["APP_ENV"] == "development"
    assert environment["DATABASE_URL"] == f"sqlite:///{expected.as_posix()}"
    assert "postgres" not in environment["DATABASE_URL"].casefold()
    assert dev_database_path(tmp_path) == expected
    assert len(environment["SECRET_KEY"]) >= 32


def test_server_settings_require_database_url(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "s" * 64)
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="finance-dev ou finance-server"):
        get_server_settings()


def test_secure_config_does_not_persist_plaintext_secrets(tmp_path):
    protect = lambda value: b"protected:" + value[::-1]
    unprotect = lambda value: value.removeprefix(b"protected:")[::-1]
    store = SecureServerConfigStore(
        tmp_path, protect=protect, unprotect=unprotect
    )
    connection = ServerConnectionConfig(
        "db.example", 5432, "finance", "finance_user"
    )

    store.save(connection, password="Password!123", secret_key="S" * 64)
    contents = store.path.read_text(encoding="utf-8")
    loaded_connection, password, secret_key = store.load()

    assert "Password!123" not in contents
    assert "S" * 64 not in contents
    assert "DATABASE_URL" not in contents
    assert loaded_connection == connection
    assert password == "Password!123"
    assert secret_key == "S" * 64


@pytest.mark.skipif(os.name != "nt", reason="DPAPI é específica do Windows")
def test_dpapi_round_trip_is_bound_to_current_windows_user():
    secret = b"finance-dpapi-round-trip"
    encrypted = protect_for_current_user(secret)

    assert encrypted != secret
    assert unprotect_for_current_user(encrypted) == secret


def test_postgresql_url_is_built_only_in_memory_with_escaped_password():
    connection = ServerConnectionConfig(
        "db.example", 5432, "finance", "finance.user"
    )

    url = build_postgres_url(connection, "p@ss:/?#")

    assert url.startswith("postgresql+psycopg://finance.user:")
    assert "p@ss:/?#" not in url
    assert "sslmode=require" in url


def test_alembic_accepts_encoded_postgresql_url_without_changing_sqlalchemy_url(
    monkeypatch,
):
    password = "special!%@#"
    connection = ServerConnectionConfig(
        "db.example", 5432, "finance", "finance_user"
    )
    database_url = build_postgres_url(connection, password)
    assert all(token in database_url for token in ("%21", "%25", "%40", "%23"))

    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        alembic_config = Config()
        set_alembic_database_url(alembic_config, settings.database_url)

        assert settings.database_url == database_url
        assert alembic_config.get_main_option("sqlalchemy.url") == database_url
        assert make_url(settings.database_url).password == password
    finally:
        get_settings.cache_clear()


def test_server_startup_does_not_print_database_url_or_password(monkeypatch, capsys):
    password = "special!%@#"
    connection = ServerConnectionConfig(
        "db.example", 5432, "finance", "finance_user"
    )
    database_url = build_postgres_url(connection, password)
    monkeypatch.setattr(environment_cli, "_ensure_official_venv", lambda: None)
    monkeypatch.setattr(environment_cli, "_title", lambda: None)
    monkeypatch.setattr(environment_cli, "_release_port", lambda: None)
    monkeypatch.setattr(
        environment_cli.SecureServerConfigStore,
        "load",
        lambda self: (connection, password, "S" * 64),
    )
    monkeypatch.setattr(environment_cli, "_run_alembic", lambda *args: None)
    monkeypatch.setattr(environment_cli, "_run_api", lambda environment: 0)

    assert environment_cli.run_server() == 0
    output = capsys.readouterr().out
    assert password not in output
    assert database_url not in output


def test_port_detection_parses_single_and_multiple_processes():
    single = json.dumps({
        "pid": 10, "name": "python.exe", "executable": "python.exe",
        "command_line": "uvicorn finance_server.app_factory:create_app --port 8000",
    })
    multiple = json.dumps([
        json.loads(single),
        {"pid": 11, "name": "other.exe", "executable": "other.exe",
         "command_line": "other"},
    ])

    assert [item.pid for item in parse_port_processes(single)] == [10]
    assert [item.pid for item in parse_port_processes(multiple)] == [10, 11]


def test_finance_process_signature_is_strict():
    assert is_finance_api_process(_finance_process()) is True
    assert is_finance_api_process(
        PortProcess(2, "python.exe", "python.exe", "python -m http.server 8000")
    ) is False


def test_unknown_port_owner_is_never_stopped():
    unknown = PortProcess(9, "other.exe", "other.exe", "other --port 8000")

    with pytest.raises(EnvironmentCommandError, match="Nenhum processo foi encerrado"):
        assert_safe_finance_processes((unknown,), health_ok=True)


def test_double_initialization_releases_confirmed_old_finance(monkeypatch):
    process = _finance_process()
    calls = 0
    stopped = []
    def observe():
        nonlocal calls
        calls += 1
        return (process,) if calls == 1 else ()
    monkeypatch.setattr(environment_cli, "port_processes", observe)
    monkeypatch.setattr(environment_cli, "finance_health", lambda: True)
    monkeypatch.setattr(
        environment_cli, "stop_process",
        lambda pid, *, force=False: stopped.append((pid, force)) or True,
    )

    environment_cli._release_port()

    assert stopped == [(process.pid, False)]


def test_stop_treats_process_that_disappears_before_taskkill_as_success(monkeypatch):
    class Completed:
        returncode = 128

    monkeypatch.setattr("finance_server.environment.subprocess.run", lambda *a, **k: Completed())
    monkeypatch.setattr("finance_server.environment.process_exists", lambda pid: False)

    assert stop_process(999_999) is True


def test_finance_stop_uses_graceful_shutdown_and_confirms_free_port(monkeypatch):
    process = _finance_process()
    calls = 0
    stopped = []
    def observe():
        nonlocal calls
        calls += 1
        return (process,) if calls == 1 else ()
    monkeypatch.setattr(environment_cli, "port_processes", observe)
    monkeypatch.setattr(environment_cli, "finance_health", lambda: True)
    monkeypatch.setattr(
        environment_cli, "stop_process",
        lambda pid, *, force=False: stopped.append((pid, force)) or True,
    )

    assert environment_cli.run_stop() == 0
    assert stopped == [(process.pid, False)]


def test_finance_stop_falls_back_to_force_after_revalidating_process(monkeypatch):
    process = _finance_process()
    stopped = []
    monkeypatch.setattr(environment_cli, "port_processes", lambda: (process,))
    monkeypatch.setattr(environment_cli, "finance_health", lambda: True)
    exits = iter((False, True))
    monkeypatch.setattr(
        environment_cli, "_wait_for_listener_exit", lambda pid: next(exits)
    )
    monkeypatch.setattr(environment_cli, "_listener", lambda pid: process)
    monkeypatch.setattr(
        environment_cli, "stop_process",
        lambda pid, *, force=False: stopped.append((pid, force)) or True,
    )

    environment_cli._stop_confirmed_process(process)
    assert stopped == [(process.pid, False), (process.pid, True)]


def test_finance_stop_never_forces_pid_that_changed_identity(monkeypatch):
    process = _finance_process()
    unknown = PortProcess(process.pid, "python.exe", "python.exe", "python -m other")
    stopped = []
    monkeypatch.setattr(environment_cli, "_wait_for_listener_exit", lambda pid: False)
    monkeypatch.setattr(environment_cli, "_listener", lambda pid: unknown)
    monkeypatch.setattr(
        environment_cli, "stop_process",
        lambda pid, *, force=False: stopped.append((pid, force)) or False,
    )

    with pytest.raises(EnvironmentCommandError, match="mudou de identidade"):
        environment_cli._stop_confirmed_process(process)
    assert stopped == [(process.pid, False)]


def test_finance_stop_is_idempotent_when_port_is_already_free(monkeypatch):
    monkeypatch.setattr(environment_cli, "port_processes", lambda: ())

    assert environment_cli.run_stop() == 0
    assert environment_cli.run_stop() == 0


def test_finance_dev_migrates_isolated_database_and_does_not_log_secret(
    tmp_path, monkeypatch, capsys,
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(environment_cli, "_ensure_official_venv", lambda: None)
    monkeypatch.setattr(environment_cli, "_title", lambda: None)
    monkeypatch.setattr(environment_cli, "_release_port", lambda: None)
    migrations = []
    launched = []
    monkeypatch.setattr(
        environment_cli, "_run_alembic",
        lambda arguments, environment: migrations.append((arguments, environment.copy())),
    )
    monkeypatch.setattr(
        environment_cli, "_run_api",
        lambda environment: launched.append(environment.copy()) or 0,
    )

    assert environment_cli.run_dev() == 0

    database = dev_database_path(tmp_path)
    assert migrations[0][0] == ["upgrade", "head"]
    assert migrations[0][1]["DATABASE_URL"].startswith("sqlite:///")
    assert launched[0]["DATABASE_URL"] == migrations[0][1]["DATABASE_URL"]
    assert "postgres" not in launched[0]["DATABASE_URL"].casefold()
    assert launched[0]["SECRET_KEY"] not in capsys.readouterr().out
    assert database.parent.is_dir()
