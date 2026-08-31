from __future__ import annotations

import ctypes
from getpass import getpass
import os
from pathlib import Path
import subprocess
import sys
import time

from finance_server.environment import (
    API_HOST, API_PORT, API_URL, EnvironmentCommandError, OFFICIAL_VENV,
    PROJECT_ROOT, SecureServerConfigStore, ServerConnectionConfig,
    assert_safe_finance_processes, build_postgres_url, dev_database_path,
    dev_environment, finance_health, port_processes, stop_process,
    is_finance_api_process,
)


def _title() -> None:
    if os.name == "nt":
        ctypes.windll.kernel32.SetConsoleTitleW("Python Finance")


def _ensure_official_venv() -> None:
    if Path(sys.prefix).resolve() != OFFICIAL_VENV.resolve():
        raise EnvironmentCommandError(
            f"Use o ambiente oficial: {OFFICIAL_VENV}"
        )


def _listener(pid: int):
    return next((item for item in port_processes() if item.pid == pid), None)


def _wait_for_listener_exit(pid: int, attempts: int = 8) -> bool:
    for _ in range(attempts):
        if _listener(pid) is None:
            return True
        time.sleep(0.25)
    return False


def _stop_confirmed_process(process) -> None:
    # taskkill sem /F solicita o encerramento primeiro. Uma falha também pode
    # significar que o processo desapareceu entre a detecção e esta chamada.
    stop_process(process.pid, force=False)
    if _wait_for_listener_exit(process.pid):
        return

    current = _listener(process.pid)
    if current is None:
        return
    if not is_finance_api_process(current):
        raise EnvironmentCommandError(
            f"O PID {process.pid} mudou de identidade; encerramento forçado cancelado."
        )

    print(f"Encerramento gracioso não concluiu; forçando PID {process.pid}.")
    stop_process(process.pid, force=True)
    if not _wait_for_listener_exit(process.pid):
        raise EnvironmentCommandError(
            f"Não foi possível encerrar com segurança o PID {process.pid}."
        )


def _release_port() -> None:
    processes = port_processes()
    if not processes:
        return
    assert_safe_finance_processes(processes, health_ok=finance_health())
    for process in processes:
        print(f"Encerrando API Finance anterior: PID {process.pid}")
        _stop_confirmed_process(process)
    for _ in range(20):
        if not port_processes():
            return
        time.sleep(0.25)
    raise EnvironmentCommandError(f"A porta {API_PORT} não foi liberada.")


def _run_alembic(arguments: list[str], environment: dict[str, str]) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments], cwd=PROJECT_ROOT,
        env=environment, check=True,
    )


def _run_api(environment: dict[str, str]) -> int:
    return subprocess.run(
        [
            sys.executable, "-m", "uvicorn",
            "finance_server.app_factory:create_app", "--factory",
            "--host", API_HOST, "--port", str(API_PORT),
        ],
        cwd=PROJECT_ROOT, env=environment,
    ).returncode


def run_dev() -> int:
    _ensure_official_venv()
    _title()
    _release_port()
    environment = os.environ.copy()
    environment.update(dev_environment())
    database = dev_database_path()
    database.parent.mkdir(parents=True, exist_ok=True)
    _run_alembic(["upgrade", "head"], environment)
    print("Ambiente: DEV")
    print(f"Banco: SQLite DEV ({database})")
    print(f"API: {API_URL}")
    return _run_api(environment)


def configure_server() -> int:
    _ensure_official_venv()
    store = SecureServerConfigStore()
    host = input("Host PostgreSQL: ").strip()
    port_text = input("Porta PostgreSQL [5432]: ").strip() or "5432"
    database = input("Banco PostgreSQL [postgres]: ").strip() or "postgres"
    username = input("Usuário PostgreSQL: ").strip()
    password = getpass("Senha PostgreSQL: ")
    secret_key = getpass("SECRET_KEY (mínimo 32 caracteres): ")
    if not host or not username:
        raise EnvironmentCommandError("Host e usuário PostgreSQL são obrigatórios.")
    connection = ServerConnectionConfig(host, int(port_text), database, username)
    store.save(connection, password=password, secret_key=secret_key)
    _, recovered_password, recovered_secret = store.load()
    if recovered_password != password or recovered_secret != secret_key:
        raise EnvironmentCommandError("A validação DPAPI da configuração falhou.")
    password = secret_key = recovered_password = recovered_secret = ""
    print(f"Configuração protegida salva em: {store.path}")
    print("Validação DPAPI: OK")
    return 0


def run_server() -> int:
    _ensure_official_venv()
    _title()
    connection, password, secret_key = SecureServerConfigStore().load()
    _release_port()
    environment = os.environ.copy()
    environment.update({
        "APP_ENV": "server",
        "DATABASE_URL": build_postgres_url(connection, password),
        "SECRET_KEY": secret_key,
        "FINANCE_API_URL": API_URL,
    })
    password = secret_key = ""
    _run_alembic(["current"], environment)
    _run_alembic(["check"], environment)
    print("Ambiente: SERVER")
    print("Banco: PostgreSQL central")
    print(f"API: {API_URL}")
    try:
        return _run_api(environment)
    finally:
        environment.pop("DATABASE_URL", None)
        environment.pop("SECRET_KEY", None)


def run_stop() -> int:
    processes = port_processes()
    if not processes:
        print(f"Porta {API_PORT} já está livre.")
        return 0
    assert_safe_finance_processes(processes, health_ok=finance_health())
    for process in processes:
        print(f"API Finance confirmada: PID {process.pid} ({process.name})")
        _stop_confirmed_process(process)
    for _ in range(20):
        if not port_processes():
            print(f"Porta {API_PORT} liberada.")
            return 0
        time.sleep(0.25)
    raise EnvironmentCommandError(f"A porta {API_PORT} permanece ocupada.")


def _entrypoint(operation) -> None:
    try:
        raise SystemExit(operation())
    except (EnvironmentCommandError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERRO: {error}", file=sys.stderr)
        raise SystemExit(1)


def dev_main() -> None:
    _entrypoint(run_dev)


def config_main() -> None:
    _entrypoint(configure_server)


def server_main() -> None:
    _entrypoint(run_server)


def stop_main() -> None:
    _entrypoint(run_stop)


if __name__ == "__main__":
    operations = {
        "dev": run_dev, "server-config": configure_server,
        "server": run_server, "stop": run_stop,
    }
    if len(sys.argv) != 2 or sys.argv[1] not in operations:
        print("Uso: python -m finance_server.environment_cli "
              "{dev|server-config|server|stop}", file=sys.stderr)
        raise SystemExit(2)
    _entrypoint(operations[sys.argv[1]])
