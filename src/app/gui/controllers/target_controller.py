from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import TargetDomainError
from app.gui.pages.metas import MetasPage, TargetDialog
from app.services.target_service import TargetService


class TargetController(QObject):
    def __init__(self, view: MetasPage, service: TargetService) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self.view.filter_button.clicked.connect(self.refresh)
        self.view.new_button.clicked.connect(self.open_new_dialog)
        self.view.edit_button.clicked.connect(self.open_edit_dialog)
        self.refresh_entities()
        self.refresh()

    def refresh_entities(self) -> None:
        try:
            self.view.set_entities(self.service.list_entities())
        except SQLAlchemyError:
            self.service.repository.session.rollback()
            self.view.set_entities([])

    def refresh(self) -> None:
        year, month, indicator, entity_id = self.view.selected_filters()
        try:
            result = self.service.get_target_vs_actual(year, month, indicator, entity_id)
            self.view.show_result(result)
        except (TargetDomainError, SQLAlchemyError) as error:
            self.service.repository.session.rollback()
            self.view.set_status(f"Falha ao carregar Meta x Realizado: {error}", error=True)

    def open_new_dialog(self) -> None:
        entities = self.service.list_entities()
        if not entities:
            self.view.set_status("Não há Entidades disponíveis para cadastro.", error=True)
            return
        dialog = TargetDialog(entities, self.view)
        year, month, indicator, entity_id = self.view.selected_filters()
        dialog.year.setValue(year)
        dialog.month.setValue(month)
        dialog.indicator.setCurrentIndex(dialog.indicator.findData(indicator))
        if entity_id is not None:
            dialog.entity.setCurrentIndex(dialog.entity.findData(entity_id))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        year, month, entity_id, indicator, target, actual, notes = dialog.create_values()
        try:
            self.service.create_target(
                entity_id=entity_id, year=year, month=month, indicator=indicator,
                target_value=target, actual_value=actual, notes=notes,
            )
        except TargetDomainError as error:
            self.view.set_status(str(error), error=True)
            return
        self.view.set_status("Meta cadastrada com sucesso.")
        self.refresh()

    def open_edit_dialog(self) -> None:
        target_id = self.view.selected_target_id()
        if target_id is None:
            self.view.set_status("Selecione uma Meta para editar.", error=True)
            return
        target = self.service.get_target(target_id)
        if target is None:
            self.view.set_status("Meta não encontrada.", error=True)
            return
        dialog = TargetDialog(self.service.list_entities(), self.view, target)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        value, notes = dialog.update_values()
        try:
            self.service.update_target(target.id, target_value=value, notes=notes)
        except TargetDomainError as error:
            self.view.set_status(str(error), error=True)
            return
        self.view.set_status("Meta atualizada com sucesso.")
        self.refresh()
