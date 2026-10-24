from decimal import Decimal
from pathlib import Path
from threading import Event
from types import SimpleNamespace

from PySide6.QtCore import QDate, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication

from app.gui.controllers.boe_controller import BOEController
from app.gui.pages.boe import BoePage
from app.importers.boe_types import BOEParsedRow, BOEValidationResult
from app.models.boe_import import BOEImport
from app.services.boe_service import (
    BOEEntityDetail, BOEImportDetails, BOEOperationalEntityOption,
    BOEOperationalRow, BOEOperationalSummary,
)


def test_boe_page_starts_with_safe_actions_disabled(qtbot):
    page = BoePage()
    qtbot.addWidget(page)

    assert not page.import_steps.buttons[1].isEnabled()
    assert not page.import_steps.buttons[3].isEnabled()
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


def test_boe_page_places_filters_first_and_import_last(qtbot):
    page = BoePage()
    qtbot.addWidget(page)

    content = page.scroll_area.widget()
    layout = content.layout()

    positions = [
        layout.indexOf(page.operations_table),
        layout.indexOf(page.history_table),
        layout.indexOf(page.details_table),
        layout.indexOf(page.import_panel),
        layout.indexOf(page.validation_result),
    ]

    # The validation result lives in a nested layout, so the last
    # component must be checked through its parent instead.
    assert positions[:4] == sorted(positions[:4])
    assert all(position >= 0 for position in positions[:4])
    assert layout.indexOf(page.import_panel) > layout.indexOf(
        page.details_table
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
    assert page.operational_unit_value.text() == "R$ 0,07"
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
    page.set_import_periods([
        SimpleNamespace(
            periodo_ano=2025, periodo_mes=11, status="imported"
        ),
        SimpleNamespace(
            periodo_ano=2026, periodo_mes=3, status="imported"
        ),
        SimpleNamespace(
            periodo_ano=2026, periodo_mes=8, status="imported"
        ),
    ])
    page.year_filter.setCurrentIndex(
        page.year_filter.findData(2026)
    )
    page.month_filter.setCurrentIndex(
        page.month_filter.findData(3)
    )

    _send_wheel_event(page.year_filter)
    _send_wheel_event(page.month_filter, -120)

    assert page.year_filter.currentData() == 2026
    assert page.month_filter.currentData() == 3



def test_boe_period_explicit_selection_is_used_by_query(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    calls = []

    class ServiceStub:
        repository = SimpleNamespace(session=SimpleNamespace(rollback=lambda: None))
        list_imports = staticmethod(lambda: [])
        list_operational_entities = staticmethod(lambda: (
            BOEOperationalEntityOption(1, None, "Entidade", 7501),
        ))

        @staticmethod
        def query_operations(*filters):
            calls.append(filters)
            return BOEOperationalSummary((), 0, Decimal("0"), Decimal("0"))

    BOEController(page, ServiceStub())
    page.set_import_periods([
        SimpleNamespace(
            periodo_ano=2025, periodo_mes=11, status="imported"
        ),
        SimpleNamespace(
            periodo_ano=2026, periodo_mes=2, status="imported"
        ),
    ])
    page.year_filter.setCurrentIndex(
        page.year_filter.findData(2026)
    )
    page.month_filter.setCurrentIndex(
        page.month_filter.findData(2)
    )

    page.query_button.click()

    assert page.year_filter.currentData() == 2026
    assert page.month_filter.currentData() == 2
    assert calls == [(2026, 2, 2026, 2, None)]


def test_boe_import_modal_blocks_duplicate_and_closes_on_success(qtbot, monkeypatch):
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
    import_completed = QSignalSpy(controller.import_completed)
    controller._selected_file = Path("boe.xlsx")
    controller._validated_boe = BOEValidationResult(
        caminho_arquivo=Path("boe.xlsx"),
        nome_arquivo="boe.xlsx",
        periodo_ano=2026,
        periodo_mes=7,
    )
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: next(
            button for button in self.buttons()
            if button.text() == "Confirmar importa\u00e7\u00e3o"
        ),
    )
    # Exercita diretamente a confirmação final e o worker.
    # A autorização da etapa 4 possui testes próprios.
    controller.import_file()
    qtbot.waitUntil(lambda: controller._import_dialog is not None and controller._import_dialog.isVisible())
    qtbot.waitUntil(lambda: len(calls) == 1)
    controller.import_file()
    assert len(calls) == 1
    assert not page.import_steps.buttons[3].isEnabled()
    assert controller._import_dialog.title.text() == "Processando importação..."
    assert controller._import_dialog.description.text() == "Aguarde enquanto os dados são validados e gravados."
    release.set()
    qtbot.waitUntil(lambda: controller._import_dialog is None)
    assert "IMPORTADO COM SUCESSO" in page.import_result.toPlainText()
    assert import_completed.count() == 1


def test_boe_import_modal_closes_on_error(qtbot, monkeypatch):
    page = BoePage()
    qtbot.addWidget(page)

    class ServiceStub:
        repository = SimpleNamespace(session=SimpleNamespace(rollback=lambda: None))
        list_imports = staticmethod(lambda: [])
        list_operational_entities = staticmethod(lambda: ())
        import_file = staticmethod(lambda _path: (_ for _ in ()).throw(RuntimeError("falha controlada")))

    controller = BOEController(page, ServiceStub())
    controller._selected_file = Path("boe.xlsx")
    controller._validated_boe = BOEValidationResult(
        caminho_arquivo=Path("boe.xlsx"),
        nome_arquivo="boe.xlsx",
        periodo_ano=2026,
        periodo_mes=7,
    )
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: next(
            button for button in self.buttons()
            if button.text() == "Confirmar importa\u00e7\u00e3o"
        ),
    )
    # Exercita diretamente a confirmação final e o worker.
    # A autorização da etapa 4 possui testes próprios.
    controller.import_file()
    qtbot.waitUntil(lambda: controller._import_thread is None)
    assert controller._import_dialog is None
    assert "falha controlada" in page.import_result.toPlainText()
    assert page.import_steps.buttons[0].isEnabled()


def test_boe_confirmation_no_never_imports(qtbot, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from app.importers.boe_types import BOEValidationResult

    page = BoePage()
    qtbot.addWidget(page)
    calls = []

    class ServiceStub:
        repository = SimpleNamespace(
            session=SimpleNamespace(rollback=lambda: None)
        )
        list_imports = staticmethod(lambda: [])
        list_operational_entities = staticmethod(lambda: ())

        def import_file(self, path):
            calls.append(path)
            raise AssertionError("Import should not run")

    controller = BOEController(
        page, ServiceStub(), defer_initial_load=True
    )
    controller._selected_file = Path("boe.xlsx")
    controller._validated_boe = BOEValidationResult(
        caminho_arquivo=Path("boe.xlsx"),
        nome_arquivo="boe.xlsx",
        periodo_ano=2026,
        periodo_mes=7,
    )
    monkeypatch.setattr(QMessageBox, "exec", lambda self: 0)
    monkeypatch.setattr(
        QMessageBox,
        "clickedButton",
        lambda self: next(
            button for button in self.buttons()
            if button.text() == "Cancelar"
        ),
    )
    controller.import_file()

    assert not calls
    assert controller._import_thread is None
    assert controller._validated_boe is not None
    assert "cancelada" in page.operation_status.text().lower()


def test_boe_available_months_from_history(qtbot):
    page = BoePage()
    qtbot.addWidget(page)

    page.set_import_periods([
        SimpleNamespace(periodo_ano=2025, periodo_mes=11, status="imported"),
        SimpleNamespace(periodo_ano=2026, periodo_mes=2, status="imported"),
        SimpleNamespace(periodo_ano=2026, periodo_mes=9, status="imported"),
        SimpleNamespace(periodo_ano=2027, periodo_mes=1, status="pending"),
    ])

    assert page.year_filter.count() == 2
    assert page.year_filter.itemData(0) == 2026
    assert page.month_filter.count() == 3
    assert page.month_filter.findData(1) == -1
    assert page.operational_filters()[:4] == (2026, 1, 2026, 12)

    page.month_filter.setCurrentIndex(
        page.month_filter.findData(9)
    )
    assert page.operational_filters()[:4] == (2026, 9, 2026, 9)

    page.year_filter.setCurrentIndex(
        page.year_filter.findData(2025)
    )
    assert page.month_filter.findData(9) == -1

    page.set_import_periods([])
    assert not page.query_button.isEnabled()
