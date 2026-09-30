from __future__ import annotations

import json
import subprocess
from threading import Event
from time import monotonic

import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMainWindow

from app.core.version import __version__
from app.gui.main_window import MainWindow
from app.gui.pages.administracao import AdministracaoPage
from app.services.update_service import (
    UpdateCheckResult,
    UpdateCheckUnavailableError,
    UpdateService,
    UpdateStatus,
)


def _completed(payload: dict, *, returncode: int = 0):
    return subprocess.CompletedProcess(
        args=[],
        returncode=returncode,
        stdout=json.dumps(payload),
        stderr="",
    )


def _payload(
    *,
    status="up_to_date",
    installed="1.0.0",
    latest="1.0.0",
    installable=False,
    reason=None,
):
    return {
        "status": status,
        "product_id": "finance",
        "installed_version": installed,
        "latest_version": latest,
        "update_available": status in (
            "update_available",
            "update_unavailable",
        ),
        "installable": installable,
        "reason": reason,
        "release_url": "https://example.test/release",
        "asset_name": f"Finance_Setup_{latest}.exe",
        "sha256": "a" * 64,
    }


def test_update_service_invokes_external_updater_contract():
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return _completed(_payload())

    service = UpdateService(
        command=[r"C:\Tools\ja-updater.exe"],
        runner=runner,
    )

    result = service.check()

    assert calls[0][0] == [
        r"C:\Tools\ja-updater.exe",
        "check",
        "--product",
        "finance",
    ]
    assert calls[0][1]["check"] is False
    assert calls[0][1]["capture_output"] is True
    assert result.status == UpdateStatus.UP_TO_DATE
    assert result.installed_version == "1.0.0"
    assert result.available_version == "1.0.0"


@pytest.mark.parametrize(
    ("remote_status", "expected"),
    [
        ("up_to_date", UpdateStatus.UP_TO_DATE),
        ("update_available", UpdateStatus.UPDATE_AVAILABLE),
        ("update_unavailable", UpdateStatus.UPDATE_AVAILABLE),
        ("installed_newer", UpdateStatus.INSTALLED_NEWER),
    ],
)
def test_update_service_maps_updater_status(remote_status, expected):
    def runner(_command, **_kwargs):
        return _completed(
            _payload(
                status=remote_status,
                latest=(
                    "1.1.0"
                    if remote_status in (
                        "update_available",
                        "update_unavailable",
                    )
                    else "1.0.0"
                ),
                installable=(remote_status == "update_available"),
                reason=(
                    "missing_sha256"
                    if remote_status == "update_unavailable"
                    else None
                ),
            )
        )

    result = UpdateService(
        command=["ja-updater"],
        runner=runner,
    ).check()

    assert result.status == expected


def test_missing_sha256_state_is_preserved():
    def runner(_command, **_kwargs):
        return _completed(
            _payload(
                status="update_unavailable",
                latest="1.1.0",
                installable=False,
                reason="missing_sha256",
            )
        )

    result = UpdateService(
        command=["ja-updater"],
        runner=runner,
    ).check()

    assert result.status == UpdateStatus.UPDATE_AVAILABLE
    assert result.installable is False
    assert result.reason == "missing_sha256"


def test_nonzero_updater_exit_fails_closed():
    def runner(_command, **_kwargs):
        return _completed(
            {
                "status": "error",
                "reason": "network_unavailable",
                "message": "offline",
            },
            returncode=5,
        )

    with pytest.raises(
        UpdateCheckUnavailableError,
        match="offline",
    ):
        UpdateService(
            command=["ja-updater"],
            runner=runner,
        ).check()


@pytest.mark.parametrize("stdout", ["", "not-json", "[]"])
def test_invalid_updater_output_fails_closed(stdout):
    def runner(_command, **_kwargs):
        return subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=stdout,
            stderr="",
        )

    with pytest.raises(UpdateCheckUnavailableError):
        UpdateService(
            command=["ja-updater"],
            runner=runner,
        ).check()


def test_process_failure_is_controlled():
    def runner(_command, **_kwargs):
        raise subprocess.TimeoutExpired(
            cmd="ja-updater",
            timeout=1,
        )

    with pytest.raises(UpdateCheckUnavailableError):
        UpdateService(
            command=["ja-updater"],
            runner=runner,
        ).check()


@pytest.mark.parametrize(
    ("installed", "latest", "remote_status", "expected"),
    [
        ("1.0.0", "1.0.0", "up_to_date", UpdateStatus.UP_TO_DATE),
        ("1.0.0", "1.0.1", "update_available", UpdateStatus.UPDATE_AVAILABLE),
        ("1.9.0", "1.10.0", "update_available", UpdateStatus.UPDATE_AVAILABLE),
        ("1.1.0", "1.0.9", "installed_newer", UpdateStatus.INSTALLED_NEWER),
    ],
)
def test_update_service_preserves_semantic_version_states_from_updater(
    installed,
    latest,
    remote_status,
    expected,
):
    def runner(_command, **_kwargs):
        return _completed(
            _payload(
                status=remote_status,
                installed=installed,
                latest=latest,
                installable=remote_status == "update_available",
            )
        )

    result = UpdateService(command=["ja-updater"], runner=runner).check()

    assert result.status == expected
    assert result.installed_version == installed
    assert result.available_version == latest


@pytest.mark.parametrize(
    "overrides",
    [
        {"product_id": "bookmaker"},
        {"product_id": ""},
        {"installed_version": ""},
        {"latest_version": None},
        {"status": "unknown"},
        {"status": None},
    ],
)
def test_invalid_updater_contract_payload_fails_closed(overrides):
    payload = _payload()
    payload.update(overrides)

    def runner(_command, **_kwargs):
        return _completed(payload)

    with pytest.raises(UpdateCheckUnavailableError):
        UpdateService(command=["ja-updater"], runner=runner).check()


@pytest.mark.parametrize(
    "error",
    [
        OSError("executable unavailable"),
        subprocess.TimeoutExpired(cmd="ja-updater", timeout=1),
    ],
)
def test_updater_communication_failures_have_controlled_message(error):
    def runner(_command, **_kwargs):
        raise error

    with pytest.raises(
        UpdateCheckUnavailableError,
        match="Não foi possível consultar atualizações no momento",
    ):
        UpdateService(command=["ja-updater"], runner=runner).check()


class _UpdateWindowHarness(QMainWindow):
    _check_for_updates = MainWindow._check_for_updates
    _update_succeeded = MainWindow._update_succeeded
    _update_failed = MainWindow._update_failed
    _finish_update_check = MainWindow._finish_update_check

    def __init__(self, service) -> None:
        super().__init__()

        self._update_service = service
        self._update_thread: QThread | None = None
        self._update_worker = None
        self._update_page = None
        self._update_dialog = None


class _ImmediateService:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def check(self):
        self.calls += 1
        return self.result


class _ControlledService:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.calls = 0

    def check(self):
        self.calls += 1
        self.started.set()
        self.release.wait(2)
        return UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            installed_version="1.0.0",
            available_version="1.0.1",
        )


def test_update_button_remains_manual_and_non_blocking(qtbot):
    page = AdministracaoPage()

    service = _ImmediateService(
        UpdateCheckResult(
            status=UpdateStatus.UP_TO_DATE,
            installed_version="1.0.0",
            available_version="1.0.0",
        )
    )

    window = _UpdateWindowHarness(service)

    qtbot.addWidget(page)
    qtbot.addWidget(window)

    page.check_updates_button.clicked.connect(
        lambda: window._check_for_updates(page)
    )

    assert service.calls == 0

    page.check_updates_button.click()

    qtbot.waitUntil(
        lambda: window._update_thread is None,
        timeout=3000,
    )

    assert service.calls == 1
    assert page.check_updates_button.isEnabled()
    assert (
        page.check_updates_button.text()
        == "Verificar atualizações"
    )
    assert page.status.text() == "O Finance está atualizado."


def test_update_button_is_disabled_and_concurrent_check_is_prevented(qtbot):
    page = AdministracaoPage()
    service = _ControlledService()
    window = _UpdateWindowHarness(service)

    qtbot.addWidget(page)
    qtbot.addWidget(window)
    page.check_updates_button.clicked.connect(
        lambda: window._check_for_updates(page)
    )

    assert page.check_updates_button.text() == "Verificar atualizações"
    assert service.calls == 0

    started_at = monotonic()
    page.check_updates_button.click()
    elapsed = monotonic() - started_at

    assert elapsed < 0.5
    assert service.started.wait(1)
    assert not page.check_updates_button.isEnabled()
    assert page.check_updates_button.text() == "Consultando..."

    window._check_for_updates(page)
    assert service.calls == 1

    service.release.set()
    qtbot.waitUntil(lambda: window._update_thread is None, timeout=3000)
    assert page.check_updates_button.isEnabled()
    assert page.check_updates_button.text() == "Verificar atualizações"
    assert page.status.text() == "Nova versão disponível: 1.0.1."


def test_non_installable_update_message_is_clear(qtbot):
    page = AdministracaoPage()
    window = _UpdateWindowHarness(None)

    qtbot.addWidget(page)
    qtbot.addWidget(window)

    window._update_page = page

    window._update_succeeded(
        UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            installed_version="1.0.0",
            available_version="1.1.0",
            installable=False,
            reason="missing_sha256",
        )
    )

    assert (
        page.status.text()
        == (
            "Nova versão disponível: 1.1.0. "
            "A release oficial não possui SHA-256 verificável."
        )
    )


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (
            UpdateStatus.UP_TO_DATE,
            "O Finance está atualizado.",
        ),
        (
            UpdateStatus.INSTALLED_NEWER,
            (
                "A versão instalada é mais recente "
                "que a última versão publicada."
            ),
        ),
    ],
)
def test_update_result_messages_are_preserved(
    qtbot,
    status,
    expected,
):
    page = AdministracaoPage()
    window = _UpdateWindowHarness(None)

    qtbot.addWidget(page)
    qtbot.addWidget(window)

    window._update_page = page

    window._update_succeeded(
        UpdateCheckResult(
            status=status,
            installed_version="1.0.0",
            available_version="1.0.0",
        )
    )

    assert page.status.text() == expected


def test_update_failure_message_is_controlled(qtbot):
    page = AdministracaoPage()
    window = _UpdateWindowHarness(None)

    qtbot.addWidget(page)
    qtbot.addWidget(window)
    window._update_page = page

    window._update_failed(RuntimeError("technical detail"))

    assert page.status.text() == "Não foi possível consultar atualizações no momento."
    assert "technical detail" not in page.status.text()


def test_administration_displays_installed_desktop_version_not_server_version(qtbot):
    page = AdministracaoPage()
    qtbot.addWidget(page)

    page.show_remote_information(
        {
            "version": "99.0.0",
            "environment": "SERVER",
            "database": "PostgreSQL",
        }
    )

    assert page.fields["version"].text() == __version__
