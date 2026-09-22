from __future__ import annotations

from threading import Event
from time import monotonic

import httpx
import pytest
from PySide6.QtCore import QThread
from PySide6.QtWidgets import QMainWindow

import app.services.update_service as update_module
from app.gui.main_window import MainWindow
from app.gui.pages.administracao import AdministracaoPage
from app.services.update_service import (
    UpdateCheckUnavailableError,
    UpdateService,
    UpdateStatus,
)


def _service_with_response(
    *, status_code: int = 200, json: object | None = None, content: bytes | None = None
) -> UpdateService:
    def handler(request: httpx.Request) -> httpx.Response:
        kwargs = {"status_code": status_code, "request": request}
        if content is not None:
            kwargs["content"] = content
        else:
            kwargs["json"] = json
        return httpx.Response(**kwargs)

    return UpdateService(transport=httpx.MockTransport(handler))


def _release(
    tag_name: str,
    *,
    draft: bool = False,
    prerelease: bool = False,
    html_url: str | None = None,
) -> dict:
    return {
        "tag_name": tag_name,
        "draft": draft,
        "prerelease": prerelease,
        "html_url": html_url or f"https://example.test/{tag_name}",
    }


@pytest.mark.parametrize(
    ("installed", "remote", "expected"),
    [
        ("1.0.0", "finance-v1.0.0", UpdateStatus.UP_TO_DATE),
        ("1.0.0", "finance-v1.0.1", UpdateStatus.UPDATE_AVAILABLE),
        ("1.9.0", "finance-v1.10.0", UpdateStatus.UPDATE_AVAILABLE),
        ("1.1.0", "finance-v1.0.9", UpdateStatus.INSTALLED_NEWER),
    ],
)
def test_update_service_compares_versions_semantically(
    monkeypatch, installed, remote, expected
):
    monkeypatch.setattr(update_module, "__version__", installed)
    service = _service_with_response(
        json=[_release(remote, html_url="https://example.test/release")]
    )

    result = service.check()

    assert result.status == expected
    assert result.installed_version == installed
    assert result.available_version == remote.removeprefix("finance-v")
    assert result.release_url == "https://example.test/release"


@pytest.mark.parametrize(
    "error",
    [httpx.ReadTimeout("timeout"), httpx.ConnectError("offline")],
)
def test_update_service_handles_network_failures(monkeypatch, error):
    def handler(request: httpx.Request) -> httpx.Response:
        raise error

    monkeypatch.setattr(update_module, "__version__", "1.0.0")
    service = UpdateService(transport=httpx.MockTransport(handler))

    with pytest.raises(
        UpdateCheckUnavailableError,
        match="Não foi possível consultar atualizações no momento",
    ):
        service.check()


@pytest.mark.parametrize("status_code", [404, 403, 429])
def test_update_service_handles_unavailable_github_responses(status_code):
    service = _service_with_response(status_code=status_code, json={})

    with pytest.raises(UpdateCheckUnavailableError):
        service.check()


@pytest.mark.parametrize(
    "service",
    [
        _service_with_response(content=b"not-json"),
        _service_with_response(json={}),
        _service_with_response(json=[_release("finance-vnot-a-version")]),
        _service_with_response(json=[{"tag_name": 101}]),
    ],
)
def test_update_service_rejects_invalid_remote_payload(service):
    with pytest.raises(UpdateCheckUnavailableError):
        service.check()


@pytest.mark.parametrize(
    "foreign_release",
    [
        _release("bookmaker-v9.0.0"),
        _release("other-product-v9.0.0"),
        _release("Finance-v9.0.0"),
    ],
)
def test_update_service_ignores_releases_from_other_products(foreign_release):
    service = _service_with_response(json=[foreign_release])

    with pytest.raises(UpdateCheckUnavailableError):
        service.check()


def test_update_service_selects_highest_stable_finance_release(monkeypatch):
    monkeypatch.setattr(update_module, "__version__", "1.0.0")
    service = _service_with_response(
        json=[
            _release("bookmaker-v8.0.0"),
            _release("finance-v1.2.0", html_url="https://example.test/finance-1.2.0"),
            _release("finance-v1.10.0", html_url="https://example.test/finance-1.10.0"),
            _release("finance-v1.9.0", html_url="https://example.test/finance-1.9.0"),
        ]
    )

    result = service.check()

    assert result.available_version == "1.10.0"
    assert result.release_url == "https://example.test/finance-1.10.0"


@pytest.mark.parametrize(
    "ignored",
    [
        _release("finance-v9.0.0", draft=True),
        _release("finance-v9.0.0", prerelease=True),
        _release("finance-vinvalid"),
    ],
)
def test_update_service_ignores_non_stable_or_invalid_finance_release(
    monkeypatch, ignored
):
    monkeypatch.setattr(update_module, "__version__", "1.0.0")
    service = _service_with_response(
        json=[ignored, _release("finance-v1.0.1")]
    )

    result = service.check()

    assert result.available_version == "1.0.1"


def test_update_service_reports_absence_of_valid_finance_release():
    service = _service_with_response(
        json=[
            _release("bookmaker-v1.0.0"),
            _release("finance-v2.0.0", draft=True),
            _release("finance-vbad"),
        ]
    )

    with pytest.raises(UpdateCheckUnavailableError):
        service.check()


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


class _ControlledService:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()
        self.calls = 0

    def check(self):
        self.calls += 1
        self.started.set()
        self.release.wait(2)
        return update_module.UpdateCheckResult(
            status=UpdateStatus.UPDATE_AVAILABLE,
            installed_version="1.0.0",
            available_version="1.0.1",
        )


def test_update_button_is_manual_non_blocking_and_disabled_while_running(qtbot):
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
    page.check_updates_button.click()
    assert service.calls == 1

    service.release.set()
    qtbot.waitUntil(lambda: window._update_thread is None, timeout=3000)
    assert page.check_updates_button.isEnabled()
    assert page.check_updates_button.text() == "Verificar atualizações"
    assert page.status.text() == "Nova versão disponível: 1.0.1."


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (UpdateStatus.UP_TO_DATE, "O Finance está atualizado."),
        (
            UpdateStatus.INSTALLED_NEWER,
            "A versão instalada é mais recente que a última versão publicada.",
        ),
    ],
)
def test_update_result_messages_are_clear(qtbot, status, expected):
    page = AdministracaoPage()
    window = _UpdateWindowHarness(None)
    qtbot.addWidget(page)
    qtbot.addWidget(window)
    window._update_page = page

    window._update_succeeded(
        update_module.UpdateCheckResult(
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

    assert page.fields["version"].text() == update_module.__version__
