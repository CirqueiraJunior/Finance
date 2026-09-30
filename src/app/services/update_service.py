from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Callable, Sequence


class UpdateStatus(StrEnum):
    UP_TO_DATE = "UP_TO_DATE"
    UPDATE_AVAILABLE = "UPDATE_AVAILABLE"
    INSTALLED_NEWER = "INSTALLED_NEWER"


@dataclass(frozen=True, slots=True)
class UpdateCheckResult:
    status: UpdateStatus
    installed_version: str
    available_version: str
    release_url: str | None = None
    installable: bool = False
    reason: str | None = None
    asset_name: str | None = None
    sha256: str | None = None


class UpdateCheckUnavailableError(RuntimeError):
    """Raised when the standalone updater cannot be consulted safely."""


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]


def _resolve_updater_command() -> tuple[str, ...]:
    configured = os.environ.get("JA_UPDATER_EXECUTABLE", "").strip()

    if configured:
        executable = Path(configured).expanduser()

        if not executable.is_file():
            raise UpdateCheckUnavailableError(
                "J.A. Updater configurado não foi encontrado."
            )

        return (str(executable),)

    program_files = os.environ.get("PROGRAMFILES", "").strip()

    if program_files:
        installed = (
            Path(program_files)
            / "J.A. Technology"
            / "J.A. Updater"
            / "J.A. Updater.exe"
        )

        if installed.is_file():
            return (str(installed),)

    discovered = shutil.which("ja-updater")

    if discovered:
        return (discovered,)

    raise UpdateCheckUnavailableError(
        "J.A. Updater não está disponível neste ambiente."
    )


class UpdateService:
    def __init__(
        self,
        *,
        command: Sequence[str] | None = None,
        timeout: float = 15.0,
        runner: ProcessRunner = subprocess.run,
    ) -> None:
        self.command = tuple(command) if command is not None else None
        self.timeout = timeout
        self.runner = runner

    def check(self) -> UpdateCheckResult:
        base_command = (
            self.command
            if self.command is not None
            else _resolve_updater_command()
        )

        command = [
            *base_command,
            "check",
            "--product",
            "finance",
        ]

        try:
            completed = self.runner(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self.timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as error:
            raise UpdateCheckUnavailableError(
                "Não foi possível consultar atualizações no momento."
            ) from error

        stdout = str(completed.stdout or "").strip()

        try:
            payload = json.loads(stdout)
        except (json.JSONDecodeError, TypeError) as error:
            raise UpdateCheckUnavailableError(
                "O J.A. Updater retornou uma resposta inválida."
            ) from error

        if not isinstance(payload, dict):
            raise UpdateCheckUnavailableError(
                "O J.A. Updater retornou uma resposta inválida."
            )

        if completed.returncode != 0:
            message = str(
                payload.get("message")
                or "Não foi possível consultar atualizações no momento."
            ).strip()

            raise UpdateCheckUnavailableError(message)

        return self._result_from_payload(payload)

    @staticmethod
    def _result_from_payload(payload: dict) -> UpdateCheckResult:
        product_id = str(payload.get("product_id") or "").strip().casefold()

        if product_id != "finance":
            raise UpdateCheckUnavailableError(
                "O J.A. Updater retornou um produto inválido."
            )

        installed = str(payload.get("installed_version") or "").strip()
        available = str(payload.get("latest_version") or "").strip()

        if not installed or not available:
            raise UpdateCheckUnavailableError(
                "O J.A. Updater retornou versões inválidas."
            )

        raw_status = str(payload.get("status") or "").strip().casefold()

        if raw_status == "up_to_date":
            status = UpdateStatus.UP_TO_DATE
        elif raw_status in ("update_available", "update_unavailable"):
            status = UpdateStatus.UPDATE_AVAILABLE
        elif raw_status == "installed_newer":
            status = UpdateStatus.INSTALLED_NEWER
        else:
            raise UpdateCheckUnavailableError(
                "O J.A. Updater retornou um estado inválido."
            )

        release_url = payload.get("release_url")
        if not isinstance(release_url, str):
            release_url = None

        asset_name = payload.get("asset_name")
        if not isinstance(asset_name, str):
            asset_name = None

        sha256 = payload.get("sha256")
        if not isinstance(sha256, str):
            sha256 = None

        reason = payload.get("reason")
        if not isinstance(reason, str):
            reason = None

        return UpdateCheckResult(
            status=status,
            installed_version=installed,
            available_version=available,
            release_url=release_url,
            installable=payload.get("installable") is True,
            reason=reason,
            asset_name=asset_name,
            sha256=sha256,
        )
