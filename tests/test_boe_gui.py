from decimal import Decimal
from pathlib import Path
from threading import Event
from types import SimpleNamespace

from PySide6.QtCore import QDate, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from app.gui.controllers.boe_controller import BOEController
from app.gui.pages.boe import BoePage
from app.importers.boe_types import BOEParsedRow, BOEValidationResult
from app.models.boe_import import BOEImport
from app.services.boe_service import (
    BOEEntityDetail, BOEImportDetails, BOEOperationalRow, BOEOperationalSummary,
)


def test_boe_page_starts_with_safe_actions_disabled(qtbot):
    page = BoePage()
    qtbot.addWidget(page)

    assert not page.validate_button.isEnabled()
    assert not page.import_button.isEnabled()
    assert page.history_table.columnCount() == 6
    assert page.details_table.columnCount() == 4
    assert page.operations_table.columnCount() == 5
    assert page.operations_table.horizontalHeaderItem(4).text() == "Valor Total"
    assert all(
        page.operations_table.horizontalHeaderItem(index).text() != "Produto"
        for index in range(page.operations_table.columnCount())
    )
    assert page.details_state.text() == (
        "Selecione uma importação para visualizar o detalhamento por Entidade."
    )


def test_boe_page_places_details_between_history_and_operational_query(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    content_layout = page.scroll_area.widget().layout()

    assert content_layout.indexOf(page.history_table) < content_layout.indexOf(
        page.details_state
    )
    assert content_layout.indexOf(page.details_state) < content_layout.indexOf(
        page.details_table
    )
    assert content_layout.indexOf(page.details_table) < content_layout.indexOf(
        page.operations_table
    )


def test_boe_page_displays_validation_result(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    result = BOEValidationResult(
        caminho_arquivo=Path("BOE - 07.26.xlsx"),
        nome_arquivo="BOE - 07.26.xlsx",
        periodo_ano=2026,
        periodo_mes=7,
        linhas=[BOEParsedRow(5, 7501, "CDL GOIANIA/GO", 100, Decimal("6.9300"))],
    )

    page.show_validation(result)

    text = page.validation_result.toPlainText()
    assert "Status: APROVADO" in text
    assert "Período: 07/2026" in text
    assert "R$ 6,93" in text


def test_boe_page_displays_import_history(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    imported = BOEImport(
        periodo_ano=2026,
        periodo_mes=7,
        nome_arquivo="BOE - 07.26.xlsx",
        caminho_origem="C:/imports/BOE - 07.26.xlsx",
        hash_arquivo="a" * 64,
        quantidade_entidades=77,
        quantidade_inconsistencias=1,
        valor_total=Decimal("21967.2684"),
        status="imported",
    )

    page.show_history([imported])

    assert page.history_table.rowCount() == 1
    assert page.history_table.item(0, 0).text() == "07/2026"
    assert page.history_table.item(0, 4).text() == "R$ 21.967,27"


def test_boe_page_displays_selected_import_details(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    imported = BOEImport(
        id=42,
        periodo_ano=2026,
        periodo_mes=7,
        nome_arquivo="BOE - 07.26.xlsx",
        caminho_origem="C:/imports/BOE - 07.26.xlsx",
        hash_arquivo="b" * 64,
        quantidade_entidades=2,
        quantidade_inconsistencias=0,
        valor_total=Decimal("20.7900"),
        status="imported",
    )
    details = BOEImportDetails(
        boe_import=imported,
        entities=(
            BOEEntityDetail(
                code=7501,
                entity_name="Entidade oficial",
                source_name="ENTIDADE ORIGEM",
                queries=1000,
                value=Decimal("69.3000"),
            ),
        ),
        total_entities=1,
        total_queries=1000,
        total_value=Decimal("69.3000"),
        inconsistencies=(),
    )

    page.show_history([imported])
    page.history_table.selectRow(0)
    page.show_details(details)

    assert page.selected_import_id() == 42
    assert page.details_table.rowCount() == 1
    assert page.details_table.item(0, 0).text() == "7501"
    assert page.details_table.item(0, 1).text() == "Entidade oficial"
    assert page.details_table.item(0, 2).text() == "1.000"
    assert page.details_table.item(0, 3).text() == "R$ 69,30"
    assert page.entities_total.text() == "1"
    assert page.queries_total.text() == "1.000"
    assert page.value_total.text() == "R$ 69,30"


def test_boe_page_shows_empty_detail_state(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    imported = BOEImport(
        id=43,
        periodo_ano=2026,
        periodo_mes=8,
        nome_arquivo="BOE - 08.26.xlsx",
        caminho_origem="C:/imports/BOE - 08.26.xlsx",
        hash_arquivo="c" * 64,
        quantidade_entidades=0,
        quantidade_inconsistencias=0,
        valor_total=Decimal("0.0000"),
        status="imported",
    )
    details = BOEImportDetails(imported, (), 0, 0, Decimal("0.0000"), ())

    page.show_details(details)

    assert page.details_table.rowCount() == 0
    assert page.details_state.text() == (
        "Nenhum detalhamento por Entidade disponível para esta importação."
    )


def test_boe_controller_loads_detail_when_history_row_is_selected(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    imported = BOEImport(
        id=44,
        periodo_ano=2026,
        periodo_mes=7,
        nome_arquivo="BOE - 07.26.xlsx",
        caminho_origem="C:/imports/BOE - 07.26.xlsx",
        hash_arquivo="d" * 64,
        quantidade_entidades=1,
        quantidade_inconsistencias=0,
        valor_total=Decimal("6.9300"),
        status="imported",
    )
    details = BOEImportDetails(
        imported,
        (BOEEntityDetail(7501, "Entidade", "ENTIDADE", 100, Decimal("6.9300")),),
        1,
        100,
        Decimal("6.9300"),
        (),
    )

    class ServiceStub:
        repository = SimpleNamespace(session=SimpleNamespace(rollback=lambda: None))

        @staticmethod
        def list_imports():
            return [imported]

        @staticmethod
        def get_import_details(import_id):
            return details if import_id == 44 else None

    BOEController(page, ServiceStub())

    page.history_table.selectRow(0)

    assert page.details_table.rowCount() == 1
    assert page.details_table.item(0, 0).text() == "7501"


def test_boe_page_shows_operational_kpis_and_rows(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    summary = BOEOperationalSummary(
        (BOEOperationalRow(2026, 7, 1, "Entidade", 100, Decimal("0.0693"), Decimal("6.9300")),),
        100, Decimal("0.0693"), Decimal("6.9300"),
    )

    page.show_operations(summary)

    assert page.operations_table.item(0, 0).text() == "07/2026"
    assert page.operations_table.item(0, 1).text() == "Entidade"
    assert page.operational_queries.text() == "100"
    assert page.operational_unit_value.text() == "R$ 0,0693"
    assert page.operational_total_value.text() == "R$ 6,93"


def _send_wheel_event(widget, delta: int = 120) -> None:
    center = widget.rect().center()
    event = QWheelEvent(
        QPointF(center),
        QPointF(widget.mapToGlobal(center)),
        QPoint(),
        QPoint(0, delta),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.ScrollUpdate,
        False,
    )
    QApplication.sendEvent(widget, event)


def test_boe_period_filters_ignore_mouse_wheel(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    page.start_period.setDate(QDate(2026, 3, 1))
    page.end_period.setDate(QDate(2026, 8, 1))

    _send_wheel_event(page.start_period)
    _send_wheel_event(page.end_period, -120)

    assert page.start_period.date() == QDate(2026, 3, 1)
    assert page.end_period.date() == QDate(2026, 8, 1)


def test_boe_period_explicit_selection_is_used_by_query(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    calls = []

    class ServiceStub:
        repository = SimpleNamespace(session=SimpleNamespace(rollback=lambda: None))
        list_imports = staticmethod(lambda: [])
        list_operational_entities = staticmethod(lambda: ())

        @staticmethod
        def query_operations(*filters):
            calls.append(filters)
            return BOEOperationalSummary((), 0, Decimal("0"), Decimal("0"))

    BOEController(page, ServiceStub())
    page.start_period.setDate(QDate(2025, 11, 1))
    page.end_period.setDate(QDate(2026, 2, 1))

    page.query_button.click()

    assert page.start_period.calendarPopup()
    assert page.end_period.calendarPopup()
    assert calls == [(2025, 11, 2026, 2, None)]


def test_boe_import_modal_blocks_duplicate_and_closes_on_success(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    release = Event()
    calls = []
    imported = BOEImport(id=1, periodo_ano=2026, periodo_mes=7, nome_arquivo="boe.xlsx",
        caminho_origem="boe.xlsx", hash_arquivo="e" * 64, quantidade_entidades=0,
        quantidade_inconsistencias=0, valor_total=Decimal("0"), status="imported")

    class ServiceStub:
        repository = SimpleNamespace(session=SimpleNamespace(rollback=lambda: None))
        list_imports = staticmethod(lambda: [])
        list_operational_entities = staticmethod(lambda: ())
        def import_file(self, _path):
            calls.append(1)
            release.wait(2)
            return imported

    controller = BOEController(page, ServiceStub())
    controller._selected_file = Path("boe.xlsx")
    page.import_button.setEnabled(True)
    page.import_button.click()
    qtbot.waitUntil(lambda: controller._import_dialog is not None and controller._import_dialog.isVisible())
    qtbot.waitUntil(lambda: len(calls) == 1)
    controller.import_file()
    assert len(calls) == 1
    assert not page.import_button.isEnabled()
    assert controller._import_dialog.title.text() == "Processando importação..."
    assert controller._import_dialog.description.text() == "Aguarde enquanto os dados são validados e gravados."
    release.set()
    qtbot.waitUntil(lambda: controller._import_dialog is None)
    assert "IMPORTADO COM SUCESSO" in page.import_result.toPlainText()


def test_boe_import_modal_closes_on_error(qtbot):
    page = BoePage()
    qtbot.addWidget(page)

    class ServiceStub:
        repository = SimpleNamespace(session=SimpleNamespace(rollback=lambda: None))
        list_imports = staticmethod(lambda: [])
        list_operational_entities = staticmethod(lambda: ())
        import_file = staticmethod(lambda _path: (_ for _ in ()).throw(RuntimeError("falha controlada")))

    controller = BOEController(page, ServiceStub())
    controller._selected_file = Path("boe.xlsx")
    page.import_button.setEnabled(True)
    page.import_button.click()
    qtbot.waitUntil(lambda: controller._import_thread is None)
    assert controller._import_dialog is None
    assert "falha controlada" in page.import_result.toPlainText()
    assert page.select_button.isEnabled()
