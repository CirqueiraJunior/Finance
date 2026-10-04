from __future__ import annotations

import json
import subprocess
from threading import Event
from time import monotonic

import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMainWindow, QMessageBox

import app.services.update_service as update_module
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
    assert calls[0][1]["creationflags"] == getattr(
        subprocess,
        "CREATE_NO_WINDOW",
        0,
    )
    assert result.status == UpdateStatus.UP_TO_DATE
    assert result.installed_version == "1.0.0"
    assert result.available_version == "1.0.0"


def test_configured_updater_has_priority(monkeypatch, tmp_path):
    configured = tmp_path / "configured" / "J.A. Updater.exe"
    configured.parent.mkdir()
    configured.touch()
    official = (
        tmp_path
        / "Program Files"
        / "J.A. Technology"
        / "J.A. Updater"
        / "J.A. Updater.exe"
    )
    official.parent.mkdir(parents=True)
    official.touch()
    calls = []

    monkeypatch.setenv("JA_UPDATER_EXECUTABLE", str(configured))
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "Program Files"))
    monkeypatch.setattr(
        update_module.shutil,
        "which",
        lambda _name: str(tmp_path / "path" / "ja-updater.exe"),
    )

    def runner(command, **_kwargs):
        calls.append(command)
        return _completed(_payload())

    UpdateService(runner=runner).check()

    assert calls == [
        [str(configured), "check", "--product", "finance"]
    ]


def test_missing_configured_updater_fails_closed_without_fallback(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv(
        "JA_UPDATER_EXECUTABLE",
        str(tmp_path / "missing" / "J.A. Updater.exe"),
    )
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.setattr(
        update_module.shutil,
        "which",
        lambda _name: pytest.fail("PATH fallback must not be consulted"),
    )

    with pytest.raises(
        UpdateCheckUnavailableError,
        match="J.A. Updater configurado não foi encontrado",
    ):
        UpdateService().check()


def test_official_program_files_updater_is_selected(monkeypatch, tmp_path):
    official = (
        tmp_path
        / "J.A. Technology"
        / "J.A. Updater"
        / "J.A. Updater.exe"
    )
    official.parent.mkdir(parents=True)
    official.touch()
    calls = []

    monkeypatch.delenv("JA_UPDATER_EXECUTABLE", raising=False)
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.setattr(
        update_module.shutil,
        "which",
        lambda _name: pytest.fail("PATH fallback must not be consulted"),
    )

    def runner(command, **_kwargs):
        calls.append(command)
        return _completed(_payload())

    UpdateService(runner=runner).check()

    assert calls == [
        [str(official), "check", "--product", "finance"]
    ]


def test_path_updater_is_used_only_after_previous_locations(monkeypatch, tmp_path):
    discovered = str(tmp_path / "path" / "ja-updater.exe")
    calls = []

    monkeypatch.delenv("JA_UPDATER_EXECUTABLE", raising=False)
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "empty-program-files"))
    monkeypatch.setattr(update_module.shutil, "which", lambda _name: discovered)

    def runner(command, **_kwargs):
        calls.append(command)
        return _completed(_payload())

    UpdateService(runner=runner).check()

    assert calls == [
        [discovered, "check", "--product", "finance"]
    ]


def test_missing_updater_in_all_locations_fails_closed(monkeypatch, tmp_path):
    monkeypatch.delenv("JA_UPDATER_EXECUTABLE", raising=False)
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path / "empty-program-files"))
    monkeypatch.setattr(update_module.shutil, "which", lambda _name: None)

    with pytest.raises(
        UpdateCheckUnavailableError,
        match="J.A. Updater não está disponível neste ambiente",
    ):
        UpdateService().check()


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
    _start_update = MainWindow._start_update
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


def test_launch_update_starts_confirmed_detached_updater():
    calls = []

    def starter(command, **kwargs):
        calls.append((command, kwargs))
        return object()

    service = UpdateService(
        command=[r"C:\Tools\J.A. Updater.exe"],
        starter=starter,
    )

    service.launch_update()

    assert calls[0][0] == [
        r"C:\Tools\J.A. Updater.exe",
        "update",
        "--product",
        "finance",
        "--confirmed",
    ]

    kwargs = calls[0][1]

    assert kwargs["stdin"] is subprocess.DEVNULL
    assert kwargs["stdout"] is subprocess.DEVNULL
    assert kwargs["stderr"] is subprocess.DEVNULL
    assert kwargs["close_fds"] is True

    expected_flags = (
        getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
        | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )

    assert kwargs["creationflags"] == expected_flags


def test_launch_update_uses_same_official_updater_resolution(
    monkeypatch,
    tmp_path,
):
    official = (
        tmp_path
        / "J.A. Technology"
        / "J.A. Updater"
        / "J.A. Updater.exe"
    )
    official.parent.mkdir(parents=True)
    official.touch()

    calls = []

    monkeypatch.delenv("JA_UPDATER_EXECUTABLE", raising=False)
    monkeypatch.setenv("PROGRAMFILES", str(tmp_path))
    monkeypatch.setattr(
        update_module.shutil,
        "which",
        lambda _name: pytest.fail("PATH fallback must not be consulted"),
    )

    def starter(command, **_kwargs):
        calls.append(command)
        return object()

    UpdateService(starter=starter).launch_update()

    assert calls == [[
        str(official),
        "update",
        "--product",
        "finance",
        "--confirmed",
    ]]


def test_launch_update_failure_is_controlled():
    def starter(_command, **_kwargs):
        raise OSError("blocked")

    with pytest.raises(
        UpdateCheckUnavailableError,
        match="Não foi possível iniciar a atualização",
    ):
        UpdateService(
            command=["ja-updater"],
            starter=starter,
        ).launch_update()


def test_installable_update_exposes_update_now_action(qtbot):
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
            installable=True,
        )
    )

    assert not page.update_now_button.isHidden()
    assert page.update_now_button.isEnabled()
    assert page.update_now_button.text() == "Atualizar agora para 1.1.0"


def test_non_installable_update_hides_update_now_action(qtbot):
    page = AdministracaoPage()
    window = _UpdateWindowHarness(None)

    qtbot.addWidget(page)
    qtbot.addWidget(window)

    window._update_page = page
    page.set_update_available(True, "1.1.0")

    window._update_succeeded(
        UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            installed_version="1.0.0",
            available_version="1.1.0",
            installable=False,
            reason="missing_sha256",
        )
    )

    assert not page.update_now_button.isVisible()
    assert not page.update_now_button.isEnabled()


def test_confirmed_update_launches_updater_and_closes_window(
    qtbot,
    monkeypatch,
):
    page = AdministracaoPage()

    class Service:
        def __init__(self):
            self.calls = 0

        def launch_update(self):
            self.calls += 1

    service = Service()
    window = _UpdateWindowHarness(service)

    qtbot.addWidget(page)
    qtbot.addWidget(window)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.Yes,
    )

    closed = []

    monkeypatch.setattr(
        window,
        "close",
        lambda: closed.append(True),
    )

    window._start_update(page)

    assert service.calls == 1
    assert closed == [True]


def test_cancelled_update_does_not_launch_updater(
    qtbot,
    monkeypatch,
):
    page = AdministracaoPage()

    class Service:
        def __init__(self):
            self.calls = 0

        def launch_update(self):
            self.calls += 1

    service = Service()
    window = _UpdateWindowHarness(service)

    qtbot.addWidget(page)
    qtbot.addWidget(window)

    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *_args, **_kwargs: QMessageBox.StandardButton.No,
    )

    window._start_update(page)

    assert service.calls == 0
