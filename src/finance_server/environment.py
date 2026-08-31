from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import secrets
import subprocess
from typing import Callable
from urllib.parse import quote
from urllib.request import urlopen


API_HOST = "127.0.0.1"
API_PORT = 8000
API_URL = f"http://{API_HOST}:{API_PORT}"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_VENV = Path.home() / ".venvs" / "Finance"


class EnvironmentCommandError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PortProcess:
    pid: int
    name: str
    executable: str
    command_line: str


@dataclass(frozen=True, slots=True)
class ServerConnectionConfig:
    host: str
    port: int
    database: str
    username: str
    sslmode: str = "require"


def local_data_root(local_appdata: str | Path | None = None) -> Path:
    raw_base = str(local_appdata or os.getenv("LOCALAPPDATA", "")).strip()
    if not raw_base:
        raise EnvironmentCommandError("LOCALAPPDATA não está disponível.")
    base = Path(raw_base).expanduser()
    return base / "J.A. Technology" / "Finance"


def dev_database_path(local_appdata: str | Path | None = None) -> Path:
    return local_data_root(local_appdata) / "dev" / "finance_dev.db"


def sqlite_url(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def dev_environment(local_appdata: str | Path | None = None) -> dict[str, str]:
    database = dev_database_path(local_appdata)
    return {
        "APP_ENV": "development",
        "DATABASE_URL": sqlite_url(database),
        "SECRET_KEY": secrets.token_urlsafe(48),
        "FINANCE_API_URL": API_URL,
    }


def build_postgres_url(
    config: ServerConnectionConfig, password: str
) -> str:
    user = quote(config.username, safe="")
    protected_password = quote(password, safe="")
    database = quote(config.database, safe="")
    sslmode = quote(config.sslmode, safe="")
    return (
        f"postgresql+psycopg://{user}:{protected_password}@"
        f"{config.host}:{config.port}/{database}?sslmode={sslmode}"
    )


class _DataBlob(ctypes.Structure):
    _fields_ = (("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte)))


def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return (
        _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))),
        buffer,
    )


def protect_for_current_user(data: bytes) -> bytes:
    if os.name != "nt":
        raise EnvironmentCommandError("DPAPI está disponível somente no Windows.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptProtectData.argtypes = (
        ctypes.POINTER(_DataBlob), wintypes.LPCWSTR, ctypes.POINTER(_DataBlob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    )
    crypt32.CryptProtectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel32.LocalFree.restype = ctypes.c_void_p
    source, source_buffer = _blob(data)
    destination = _DataBlob()
    if not crypt32.CryptProtectData(
        ctypes.byref(source), "Finance", None, None, None, 0x1,
        ctypes.byref(destination),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(destination.pbData, ctypes.c_void_p))
        del source_buffer


def unprotect_for_current_user(data: bytes) -> bytes:
    if os.name != "nt":
        raise EnvironmentCommandError("DPAPI está disponível somente no Windows.")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = (
        ctypes.POINTER(_DataBlob), ctypes.c_void_p, ctypes.POINTER(_DataBlob),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    )
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel32.LocalFree.restype = ctypes.c_void_p
    source, source_buffer = _blob(data)
    destination = _DataBlob()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None, 0x1,
        ctypes.byref(destination),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(ctypes.cast(destination.pbData, ctypes.c_void_p))
        del source_buffer


class SecureServerConfigStore:
    def __init__(
        self,
        root: Path | None = None,
        *,
        protect: Callable[[bytes], bytes] = protect_for_current_user,
        unprotect: Callable[[bytes], bytes] = unprotect_for_current_user,
    ) -> None:
        self.path = (root or local_data_root()) / "server_config.json"
        self._protect = protect
        self._unprotect = unprotect

    def save(
        self,
        connection: ServerConnectionConfig,
        *,
        password: str,
        secret_key: str,
    ) -> None:
        if not password:
            raise EnvironmentCommandError("A senha PostgreSQL é obrigatória.")
        if len(secret_key) < 32:
            raise EnvironmentCommandError(
                "SECRET_KEY deve possuir ao menos 32 caracteres."
            )
        payload = {
            "version": 1,
            "connection": asdict(connection),
            "password_dpapi": b64encode(
                self._protect(password.encode("utf-8"))
            ).decode("ascii"),
            "secret_key_dpapi": b64encode(
                self._protect(secret_key.encode("utf-8"))
            ).decode("ascii"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)

    def load(self) -> tuple[ServerConnectionConfig, str, str]:
        if not self.path.is_file():
            raise EnvironmentCommandError(
                "Configuração central ausente. Execute finance-server-config."
            )
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            connection = ServerConnectionConfig(**payload["connection"])
            password = self._unprotect(
                b64decode(payload["password_dpapi"], validate=True)
            ).decode("utf-8")
            secret_key = self._unprotect(
                b64decode(payload["secret_key_dpapi"], validate=True)
            ).decode("utf-8")
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise EnvironmentCommandError(
                "Configuração central inválida ou inacessível ao usuário Windows atual."
            ) from error
        if not password or len(secret_key) < 32:
            raise EnvironmentCommandError("Configuração central protegida é inválida.")
        return connection, password, secret_key


def is_finance_api_process(process: PortProcess) -> bool:
    command = process.command_line.casefold()
    executable = process.executable.casefold()
    return (
        "python" in (process.name.casefold() + executable)
        and "uvicorn" in command
        and "finance_server.app_factory:create_app" in command
        and "--port 8000" in command
    )


def parse_port_processes(raw: str) -> tuple[PortProcess, ...]:
    if not raw.strip():
        return ()
    payload = json.loads(raw)
    rows = payload if isinstance(payload, list) else [payload]
    return tuple(
        PortProcess(
            int(row["pid"]), str(row.get("name") or ""),
            str(row.get("executable") or ""), str(row.get("command_line") or ""),
        )
        for row in rows
    )


def port_processes(port: int = API_PORT) -> tuple[PortProcess, ...]:
    script = (
        f"$items = Get-NetTCPConnection -LocalPort {port} -State Listen "
        "-ErrorAction SilentlyContinue | ForEach-Object { "
        "$p = Get-CimInstance Win32_Process -Filter \"ProcessId=$($_.OwningProcess)\"; "
        "[pscustomobject]@{pid=$_.OwningProcess;name=$p.Name;"
        "executable=$p.ExecutablePath;command_line=$p.CommandLine} }; "
        "$items | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
        check=True, capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return parse_port_processes(completed.stdout)


def finance_health(timeout: float = 1.5) -> bool:
    try:
        with urlopen(f"{API_URL}/health", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return payload.get("status") == "ok" and bool(payload.get("version"))
    except Exception:
        return False


def assert_safe_finance_processes(
    processes: tuple[PortProcess, ...], *, health_ok: bool
) -> None:
    if not processes:
        return
    if not health_ok or not all(is_finance_api_process(item) for item in processes):
        summary = ", ".join(f"PID {item.pid} ({item.name})" for item in processes)
        raise EnvironmentCommandError(
            f"Porta {API_PORT} ocupada por processo não confirmado: {summary}. "
            "Nenhum processo foi encerrado."
        )


def process_exists(pid: int) -> bool:
    completed = subprocess.run(
        [
            "powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
            f"if (Get-Process -Id {pid} -ErrorAction SilentlyContinue) {{ exit 0 }} "
            "else { exit 1 }",
        ],
        capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return completed.returncode == 0


def stop_process(pid: int, *, force: bool = False) -> bool:
    arguments = ["taskkill.exe", "/PID", str(pid), "/T"]
    if force:
        arguments.append("/F")
    completed = subprocess.run(
        arguments, capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return completed.returncode == 0 or not process_exists(pid)
