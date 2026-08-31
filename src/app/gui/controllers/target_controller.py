from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import TargetDomainError
from app.api_client import APIReadTimeoutError
from app.gui.pages.metas import (
    MetasPage, TargetDialog, TargetImportProgressDialog,
)
from app.services.target_service import TargetService
from app.services.ranking_service import RankingService


class TargetImportWorker(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    finished = Signal()

    def __init__(self, service, file_path: str) -> None:
        super().__init__()
        self.service = service
        self.file_path = file_path

    @Slot()
    def run(self) -> None:
        try:
            self.succeeded.emit(self.service.import_file(self.file_path))
        except Exception as error:
            self.failed.emit(error)
        finally:
            self.finished.emit()


class TargetController(QObject):
    def __init__(self, view: MetasPage, service: TargetService,
                 ranking: RankingService | None = None) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self.ranking = ranking
        self.import_file_path = None
        self._import_thread: QThread | None = None
        self._import_worker: TargetImportWorker | None = None
        self._import_dialog: TargetImportProgressDialog | None = None
        self.view.filter_button.clicked.connect(self.refresh)
        self.view.new_button.clicked.connect(self.open_new_dialog)
        self.view.edit_button.clicked.connect(self.open_edit_dialog)
        self.view.ranking_refresh.clicked.connect(self.refresh_ranking)
        self.view.ranking_entity.currentIndexChanged.connect(self.refresh_ranking)
        self.view.import_file_button.clicked.connect(self.select_import_file)
        self.view.confirm_import_button.clicked.connect(self.import_validated_file)
        self.view.set_import_available(
            hasattr(service, "validate_import") and hasattr(service, "import_file")
        )
        self.refresh_entities()
        self.refresh()
        self.refresh_ranking()

    def select_import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.view, "Selecionar arquivo de Metas", "",
            "Planilhas Excel (*.xlsx *.xlsm)",
        )
        if not path:
            return
        self.validate_import_file(path)

    def validate_import_file(self, path: str) -> None:
        self.import_file_path = None
        self.view.confirm_import_button.setEnabled(False)
        try:
            validation = self.service.validate_import(path)
            self.view.show_import_validation(validation)
            if validation.get("can_import"):
                self.import_file_path = path
        except RuntimeError as error:
            self.view.set_status(f"Falha ao validar arquivo de Metas: {error}", error=True)

    def import_validated_file(self) -> None:
        if not self.import_file_path or (
            self._import_thread is not None and self._import_thread.isRunning()
        ):
            return
        self.view.confirm_import_button.setEnabled(False)
        self.view.import_file_button.setEnabled(False)
        self._import_dialog = TargetImportProgressDialog(self.view)
        self._import_dialog.show()

        self._import_thread = QThread(self)
        self._import_worker = TargetImportWorker(
            self.service, self.import_file_path
        )
        self._import_worker.moveToThread(self._import_thread)
        self._import_thread.started.connect(self._import_worker.run)
        self._import_worker.succeeded.connect(self._import_succeeded)
        self._import_worker.failed.connect(self._import_failed)
        self._import_worker.finished.connect(self._import_thread.quit)
        self._import_worker.finished.connect(self._import_worker.deleteLater)
        self._import_thread.finished.connect(self._import_finished)
        self._import_thread.start()

    @Slot(object)
    def _import_succeeded(self, result: dict) -> None:
        self.view.show_import_result(result)
        self.import_file_path = None
        self.refresh_entities()
        self.refresh()
        self.refresh_ranking()

    @Slot(object)
    def _import_failed(self, error: Exception) -> None:
        if isinstance(error, APIReadTimeoutError):
            self.import_file_path = None
        self.view.set_status(f"Falha ao importar Metas: {error}", error=True)

    @Slot()
    def _import_finished(self) -> None:
        if self._import_dialog is not None:
            self._import_dialog.accept()
            self._import_dialog.deleteLater()
            self._import_dialog = None
        if self._import_thread is not None:
            self._import_thread.deleteLater()
        self._import_thread = None
        self._import_worker = None
        self.view.import_file_button.setEnabled(True)
        self.view.confirm_import_button.setEnabled(
            self.import_file_path is not None
        )

    def refresh_ranking(self) -> None:
        if self.ranking is None:
            return
        try:
            year = self.view.ranking_year.value()
            rows = self.ranking.quarterly(year, self.view.ranking_quarter.currentData())
            self.view.show_ranking(rows, self.ranking.annual(year))
        except (ValueError, SQLAlchemyError, RuntimeError) as error:
            self.service.repository.session.rollback()
            self.view.set_status(f"Falha ao carregar Ranking: {error}", error=True)

    def refresh_entities(self) -> None:
        try:
            self.view.set_entities(self.service.list_entities())
        except (SQLAlchemyError, RuntimeError):
            self.service.repository.session.rollback()
            self.view.set_entities([])

    def refresh(self) -> None:
        year, month, indicator, entity_id = self.view.selected_filters()
        try:
            result = self.service.get_target_vs_actual(year, month, indicator, entity_id)
            self.view.show_result(result)
        except (TargetDomainError, SQLAlchemyError, RuntimeError) as error:
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
        dialog.month.set_month(month)
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
        except (TargetDomainError, RuntimeError) as error:
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
        except (TargetDomainError, RuntimeError) as error:
            self.view.set_status(str(error), error=True)
            return
        self.view.set_status("Meta atualizada com sucesso.")
        self.refresh()
