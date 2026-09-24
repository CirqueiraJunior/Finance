from __future__ import annotations

from base64 import b64decode, b64encode
from dataclasses import asdict
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from typing import Callable

import ntsecuritycon
import win32security

from finance_server.environment import (
    EnvironmentCommandError,
    ServerConnectionConfig,
)


CRYPTPROTECT_UI_FORBIDDEN = 0x1
CRYPTPROTECT_LOCAL_MACHINE = 0x4


class _DataBlob(ctypes.Structure):
    _fields_ = (
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    )


def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return (
        _DataBlob(
            len(data),
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
        ),
        buffer,
    )


def service_data_root(program_data: str | Path | None = None) -> Path:
    raw_base = str(program_data or os.getenv("PROGRAMDATA", "")).strip()
    if not raw_base:
        raise EnvironmentCommandError("PROGRAMDATA não está disponível.")
    return Path(raw_base).expanduser() / "J.A. Technology" / "Finance"


def protect_for_machine(data: bytes) -> bytes:
    if os.name != "nt":
        raise EnvironmentCommandError(
            "DPAPI está disponível somente no Windows."
        )

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    crypt32.CryptProtectData.argtypes = (
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    )
    crypt32.CryptProtectData.restype = wintypes.BOOL

    kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel32.LocalFree.restype = ctypes.c_void_p

    source, source_buffer = _blob(data)
    destination = _DataBlob()

    flags = CRYPTPROTECT_UI_FORBIDDEN | CRYPTPROTECT_LOCAL_MACHINE

    if not crypt32.CryptProtectData(
        ctypes.byref(source),
        "FinanceServer",
        None,
        None,
        None,
        flags,
        ctypes.byref(destination),
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(
            ctypes.cast(destination.pbData, ctypes.c_void_p)
        )
        del source_buffer


def unprotect_for_machine(data: bytes) -> bytes:
    if os.name != "nt":
        raise EnvironmentCommandError(
            "DPAPI está disponível somente no Windows."
        )

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    crypt32.CryptUnprotectData.argtypes = (
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.POINTER(_DataBlob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    )
    crypt32.CryptUnprotectData.restype = wintypes.BOOL

    kernel32.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel32.LocalFree.restype = ctypes.c_void_p

    source, source_buffer = _blob(data)
    destination = _DataBlob()

    if not crypt32.CryptUnprotectData(
        ctypes.byref(source),
        None,
        None,
        None,
        None,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(destination),
    ):
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        return ctypes.string_at(destination.pbData, destination.cbData)
    finally:
        kernel32.LocalFree(
            ctypes.cast(destination.pbData, ctypes.c_void_p)
        )
        del source_buffer



def restrict_service_acl(path: Path, *, directory: bool) -> None:
    system_sid = win32security.CreateWellKnownSid(
        win32security.WinLocalSystemSid,
        None,
    )
    administrators_sid = win32security.CreateWellKnownSid(
        win32security.WinBuiltinAdministratorsSid,
        None,
    )

    dacl = win32security.ACL()

    inheritance = (
        win32security.OBJECT_INHERIT_ACE
        | win32security.CONTAINER_INHERIT_ACE
        if directory
        else 0
    )

    for sid in (system_sid, administrators_sid):
        dacl.AddAccessAllowedAceEx(
            win32security.ACL_REVISION_DS,
            inheritance,
            ntsecuritycon.FILE_ALL_ACCESS,
            sid,
        )

    win32security.SetNamedSecurityInfo(
        str(path),
        win32security.SE_FILE_OBJECT,
        (
            win32security.DACL_SECURITY_INFORMATION
            | win32security.PROTECTED_DACL_SECURITY_INFORMATION
        ),
        None,
        None,
        dacl,
        None,
    )


class ServiceServerConfigStore:
    def __init__(
        self,
        root: Path | None = None,
        *,
        protect: Callable[[bytes], bytes] = protect_for_machine,
        unprotect: Callable[[bytes], bytes] = unprotect_for_machine,
    ) -> None:
        self.path = (root or service_data_root()) / "server_config.json"
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
            raise EnvironmentCommandError(
                "A senha PostgreSQL é obrigatória."
            )
        if len(secret_key) < 32:
            raise EnvironmentCommandError(
                "SECRET_KEY deve possuir ao menos 32 caracteres."
            )

        payload = {
            "version": 1,
            "scope": "machine",
            "connection": asdict(connection),
            "password_dpapi": b64encode(
                self._protect(password.encode("utf-8"))
            ).decode("ascii"),
            "secret_key_dpapi": b64encode(
                self._protect(secret_key.encode("utf-8"))
            ).decode("ascii"),
        }

        self.path.parent.mkdir(parents=True, exist_ok=True)
        restrict_service_acl(self.path.parent, directory=True)

        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        restrict_service_acl(temporary, directory=False)
        temporary.replace(self.path)
        restrict_service_acl(self.path, directory=False)

    def load(
        self,
    ) -> tuple[ServerConnectionConfig, str, str]:
        if not self.path.is_file():
            raise EnvironmentCommandError(
                "Configuração do serviço Finance ausente."
            )

        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8")
            )

            if payload.get("scope") != "machine":
                raise ValueError("Escopo DPAPI inválido.")

            connection = ServerConnectionConfig(
                **payload["connection"]
            )

            password = self._unprotect(
                b64decode(
                    payload["password_dpapi"],
                    validate=True,
                )
            ).decode("utf-8")

            secret_key = self._unprotect(
                b64decode(
                    payload["secret_key_dpapi"],
                    validate=True,
                )
            ).decode("utf-8")

        except (
            KeyError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            OSError,
        ) as error:
            raise EnvironmentCommandError(
                "Configuração protegida do serviço Finance "
                "é inválida ou inacessível."
            ) from error

        if not password or len(secret_key) < 32:
            raise EnvironmentCommandError(
                "Configuração protegida do serviço Finance é inválida."
            )

        return connection, password, secret_key
