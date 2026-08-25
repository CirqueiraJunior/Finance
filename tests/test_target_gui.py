from decimal import Decimal

from PySide6.QtWidgets import QAbstractItemView, QDialog

from app.gui.controllers.target_controller import TargetController
from app.gui.pages.metas import MetasPage, TargetDialog
from app.models.entity import Entity
from app.repositories.entity_repository import EntityRepository
from app.repositories.target_repository import TargetRepository
from app.services.target_service import TargetService


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

    assert page.table.columnCount() == 7
    assert page.new_button.text() == "Nova Meta"
    assert page.indicator_filter.count() == 2
    assert page.table.editTriggers() == QAbstractItemView.EditTrigger.NoEditTriggers
    assert page.empty_state.isVisibleTo(page)


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
