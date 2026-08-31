from decimal import Decimal
import threading
from types import SimpleNamespace

import httpx
import pytest
from PySide6.QtWidgets import QAbstractItemView, QDialog, QLabel

from app.api_client import APIClient, APIConnectionError, APIReadTimeoutError
from app.gui.controllers.target_controller import TargetController
from app.gui.pages.metas import (
    MetasPage, TargetDialog, TargetImportProgressDialog,
)
from app.models.entity import Entity
from app.repositories.entity_repository import EntityRepository
from app.repositories.target_repository import TargetRepository
from app.services.target_service import TargetService
from app.services.target_service import TargetSummary, TargetVsActual
from app.services.remote_services import RemoteTargetService


def make_context(db_session):
    entity = Entity(codigo_entidade=7501, nome="Goiânia")
    consolidated = Entity(codigo_entidade=7500, nome="Consolidado")
    db_session.add_all([entity, consolidated])
    db_session.commit()
    service = TargetService(
        TargetRepository(db_session), EntityRepository(db_session)
    )
    return service, entity


def test_page_has_filters_cards_table_and_empty_state(qtbot):
    page = MetasPage()
    qtbot.addWidget(page)

    assert page.table.columnCount() == 8
    assert page.table.horizontalHeaderItem(7).text() == "Observação"
    assert page.new_button.text() == "Nova Meta"
    assert page.indicator_filter.count() == 2
    assert page.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert page.empty_state.isVisibleTo(page)
    assert page.import_file_button.text() == "Importar Metas"


def test_import_preview_enables_confirmation_only_when_valid(qtbot):
    page = MetasPage()
    qtbot.addWidget(page)
    base = {
        "metadata": {"file_name": "metas.xlsx", "detected_type": "META_REALIZADO", "year": 2026},
        "preview": [{"line": 4, "entity_code": 7001, "entity_name": "Inativa",
                     "year": 2026, "month": 1, "indicator": "CONSULTAS",
                     "target": "100.0000", "actual": "80.0000"}],
        "warnings": [], "totals": {"rows": 1, "target": "100.0000", "actual": "80.0000"},
    }
    page.show_import_validation({**base, "errors": [], "can_import": True})
    assert page.confirm_import_button.isEnabled()
    assert page.import_preview.rowCount() == 1

    page.show_import_validation({
        **base, "errors": ["Duplicidade"], "can_import": False,
    })
    assert not page.confirm_import_button.isEnabled()
    assert "Duplicidade" in page.import_issues.text()


def test_dialog_has_real_indicators_and_excludes_7500(qtbot, db_session):
    service, entity = make_context(db_session)
    dialog = TargetDialog(service.list_entities())
    qtbot.addWidget(dialog)

    assert dialog.entity.count() == 1
    assert dialog.entity.currentData() == entity.id
    assert dialog.indicator.itemData(0) == "CONSULTAS"
    assert dialog.indicator.itemData(1) == "REGISTROS"


def test_controller_displays_meta_actual_cards_and_zero_target(qtbot, db_session):
    service, entity = make_context(db_session)
    service.create_target(
        entity_id=entity.id, year=2026, month=7, indicator="CONSULTAS",
        target_value="0", actual_value="10",
    )
    page = MetasPage()
    qtbot.addWidget(page)
    page.year_filter.setValue(2026)
    page.month_filter.setCurrentIndex(6)
    controller = TargetController(page, service)
    controller.refresh()

    assert page.table.rowCount() == 1
    assert page.table.item(0, 0).text() == "7501"
    assert page.table.item(0, 4).text() == "10,0000"
    assert page.table.item(0, 6).text() == "—"
    assert page.entity_count.text() == "1"
    assert page.achievement_total.text() == "—"
    assert not page.empty_state.isVisible()


def test_controller_creates_and_edits_target(qtbot, db_session, monkeypatch):
    service, entity = make_context(db_session)
    page = MetasPage()
    qtbot.addWidget(page)
    page.year_filter.setValue(2026)
    page.month_filter.setCurrentIndex(6)
    controller = TargetController(page, service)

    class Field:
        def setValue(self, _value):
            pass

        def set_month(self, _value):
            pass

        def setCurrentIndex(self, _value):
            pass

        def findData(self, _value):
            return 0

    class NewDialog:
        def __init__(self, _entities, _parent):
            self.year = Field()
            self.month = Field()
            self.indicator = Field()
            self.entity = Field()

        def exec(self):
            return QDialog.DialogCode.Accepted

        def create_values(self):
            return 2026, 7, entity.id, "CONSULTAS", "100", "80", "Teste"

    monkeypatch.setattr("app.gui.controllers.target_controller.TargetDialog", NewDialog)
    controller.open_new_dialog()
    assert page.table.rowCount() == 1
    page.table.selectRow(0)
    target = service.list_by_period(2026, 7)[0]

    class EditDialog:
        def __init__(self, _entities, _parent, _target):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def update_values(self):
            return "120", "Revisada"

    monkeypatch.setattr("app.gui.controllers.target_controller.TargetDialog", EditDialog)
    controller.open_edit_dialog()
    assert service.get_target(target.id).valor_meta == Decimal("120.0000")
    assert service.get_target(target.id).valor_realizado == Decimal("80.0000")
    assert service.get_target(target.id).observacao == "Revisada"


class _RemoteImportService:
    def __init__(self, *, result=None, error=None, wait=False):
        self.repository = SimpleNamespace(
            session=SimpleNamespace(rollback=lambda: None)
        )
        self.result = result or {
            "imported": 2, "year": 2026,
            "target_total": "220", "actual_total": "170",
        }
        self.error = error
        self.wait = wait
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0
        self.worker_thread = None
        self.refresh_calls = 0

    def validate_import(self, _path):
        return {"can_import": True}

    def import_file(self, _path):
        self.calls += 1
        self.worker_thread = threading.get_ident()
        self.started.set()
        if self.wait:
            self.release.wait(3)
        if self.error:
            raise self.error
        return self.result

    def list_entities(self):
        return []

    def get_target_vs_actual(self, *_args):
        self.refresh_calls += 1
        return TargetVsActual(
            (), TargetSummary(0, Decimal(0), Decimal(0), Decimal(0), None)
        )


class _Ranking:
    def __init__(self):
        self.calls = 0

    def quarterly(self, *_args):
        self.calls += 1
        return []

    def annual(self, *_args):
        return []


def _async_controller(qtbot, service):
    page = MetasPage()
    qtbot.addWidget(page)
    ranking = _Ranking()
    controller = TargetController(page, service, ranking)
    controller.import_file_path = "metas.xlsx"
    page.confirm_import_button.setEnabled(True)
    return page, controller, ranking


def test_import_runs_off_ui_thread_blocks_duplicate_and_refreshes(qtbot):
    service = _RemoteImportService(wait=True)
    page, controller, ranking = _async_controller(qtbot, service)
    main_thread = threading.get_ident()

    controller.import_validated_file()
    qtbot.waitUntil(service.started.is_set)

    assert service.worker_thread != main_thread
    assert not page.confirm_import_button.isEnabled()
    assert not page.import_file_button.isEnabled()
    assert isinstance(controller._import_dialog, TargetImportProgressDialog)
    assert controller._import_dialog.isVisible()
    assert controller._import_dialog.windowTitle() == "Importação de Metas"
    modal_texts = {
        label.text() for label in controller._import_dialog.findChildren(QLabel)
    }
    assert "Processando importação..." in modal_texts
    assert "Esta operação pode levar alguns instantes." in modal_texts
    assert (controller._import_dialog.progress.minimum(),
            controller._import_dialog.progress.maximum()) == (0, 0)
    controller.import_validated_file()
    assert service.calls == 1

    service.release.set()
    qtbot.waitUntil(lambda: controller._import_thread is None)

    assert controller._import_dialog is None
    assert page.import_file_button.isEnabled()
    assert not page.confirm_import_button.isEnabled()
    assert "Metas importadas com sucesso" in page.status.text()
    assert service.refresh_calls >= 2
    assert ranking.calls >= 2


@pytest.mark.parametrize(
    "error, expected, confirmation_enabled",
    [
        (RuntimeError("falha segura"), "falha segura", True),
        (APIReadTimeoutError(
            "A importação está demorando mais que o esperado. "
            "Verifique o resultado antes de tentar novamente."
        ), "Verifique o resultado antes de tentar novamente", False),
        (APIConnectionError(
            "Servidor Finance indisponível. Verifique a conexão e tente novamente."
        ), "Servidor Finance indisponível", True),
    ],
)
def test_import_error_closes_progress_and_restores_controls(
    qtbot, error, expected, confirmation_enabled,
):
    service = _RemoteImportService(error=error)
    page, controller, _ = _async_controller(qtbot, service)

    controller.import_validated_file()
    qtbot.waitUntil(lambda: controller._import_thread is None)

    assert controller._import_dialog is None
    assert page.import_file_button.isEnabled()
    assert page.confirm_import_button.isEnabled() is confirmation_enabled
    assert expected in page.status.text()
    if isinstance(error, APIReadTimeoutError):
        assert "Servidor Finance indisponível" not in page.status.text()


def test_remote_target_import_uses_specific_import_timeout_flag():
    class API:
        def upload(self, path, file_path, **kwargs):
            return path, file_path, kwargs

    path, file_path, kwargs = RemoteTargetService(API()).import_file("metas.xlsx")

    assert path == "/api/v1/targets/import"
    assert file_path == "metas.xlsx"
    assert kwargs == {"import_file": True}


@pytest.mark.parametrize(
    "transport_error, exception, message",
    [
        (httpx.ReadTimeout("demora"), APIReadTimeoutError,
         "Verifique o resultado antes de tentar novamente"),
        (httpx.ConnectError("offline"), APIConnectionError,
         "Servidor Finance indisponível. Verifique a conexão"),
    ],
)
def test_import_distinguishes_timeout_from_connection_error(
    tmp_path, monkeypatch, transport_error, exception, message,
):
    path = tmp_path / "metas.xlsx"
    path.write_bytes(b"arquivo")
    client = APIClient("http://127.0.0.1:8000")

    def fail(*_args, **_kwargs):
        raise transport_error

    monkeypatch.setattr(client._client, "request", fail)
    with pytest.raises(exception, match=message):
        client.upload("/api/v1/targets/import", str(path), import_file=True)
    client.close()
