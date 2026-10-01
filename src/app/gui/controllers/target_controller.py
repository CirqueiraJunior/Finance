from decimal import Decimal
from pathlib import Path
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QDialog, QFileDialog
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import TargetDomainError
from app.api_client import APIClient, APIReadTimeoutError
from app.gui.processing import OperationWorker, ProcessingDialog
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
        self.selected_import_file_path = None
        self._import_thread: QThread | None = None
        self._import_worker: TargetImportWorker | None = None
        self._import_dialog: TargetImportProgressDialog | None = None
        self._operation_thread: QThread | None = None
        self._operation_worker: OperationWorker | None = None
        self._operation_dialog = None
        self.view.filter_button.clicked.connect(self.refresh)
        self.view.new_button.clicked.connect(self.open_new_dialog)
        self.view.edit_button.clicked.connect(self.open_edit_dialog)
        self.view.ranking_refresh.clicked.connect(self.refresh_ranking)
        self.view.ranking_entity.currentIndexChanged.connect(self.refresh_ranking)
        self.view.import_file_button.clicked.connect(self.select_import_file)
        self.view.validate_import_button.clicked.connect(
            self.validate_selected_import_file
        )
        self.view.confirm_import_button.clicked.connect(self.import_validated_file)
        self.view.set_import_available(
            hasattr(service, "validate_import") and hasattr(service, "import_file")
        )
        self._initial_load()

    def _rollback_local(self, service=None) -> None:
        target = service or self.service
        repository = getattr(target, "repository", None)
        session = getattr(repository, "session", None)

        if session is not None:
            try:
                session.rollback()
            except Exception:
                pass

    @staticmethod
    def _has_remote_api(service) -> bool:
        return service is not None and isinstance(
            getattr(service, "api", None), APIClient
        )

    def _run_operation(
        self,
        *,
        service,
        window_title: str,
        operation,
        succeeded,
        failed,
        force_worker: bool = False,
        import_operation: bool = False,
        dialog_factory=None,
    ) -> None:
        repository = getattr(service, "repository", None)
        local_session = getattr(repository, "session", None)

        # Uma Session SQLAlchemy real nunca atravessa threads.
        # Stubs comuns permanecem síncronos para compatibilidade.
        # Importações podem forçar worker quando não usam Session real.
        if (
            isinstance(local_session, Session)
            or (
                not force_worker
                and not self._has_remote_api(service)
            )
        ):
            try:
                succeeded(operation())
            except Exception as error:
                self._rollback_local(service)
                failed(error)
            return

        if (
            self._operation_thread is not None
            and self._operation_thread.isRunning()
        ):
            return

        if dialog_factory is None:
            dialog = ProcessingDialog(
                self.view,
                window_title=window_title,
            )
        else:
            dialog = dialog_factory()

        thread = QThread(self)
        worker = OperationWorker(operation)
        worker.moveToThread(thread)

        self._operation_dialog = dialog
        self._operation_thread = thread
        self._operation_worker = worker

        if import_operation:
            self._import_dialog = dialog
            self._import_thread = thread
            self._import_worker = worker

        state = {
            "ok": False,
            "result": None,
            "error": None,
        }

        def store_success(result) -> None:
            state["ok"] = True
            state["result"] = result

        def store_failure(error) -> None:
            state["error"] = error

        def finished() -> None:
            if self._operation_dialog is not None:
                self._operation_dialog.accept()
                self._operation_dialog.deleteLater()

            if self._operation_thread is not None:
                self._operation_thread.deleteLater()

            self._operation_dialog = None
            self._operation_thread = None
            self._operation_worker = None

            if import_operation:
                self._import_dialog = None
                self._import_thread = None
                self._import_worker = None

            if state["ok"]:
                succeeded(state["result"])
            else:
                failed(state["error"])

        thread.started.connect(worker.run)
        worker.succeeded.connect(store_success)
        worker.failed.connect(store_failure)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(finished)

        dialog.show()
        thread.start()

    def _initial_load(self) -> None:
        # Carga inicial sequencial para evitar concorrência entre
        # entidades, Meta x Realizado e Ranking.
        try:
            self.view.set_entities(
                self.service.list_entities()
            )
        except (SQLAlchemyError, RuntimeError):
            self._rollback_local()
            self.view.set_entities([])

        try:
            year, month, indicator, entity_id = (
                self.view.selected_filters()
            )
            result = self._get_target_vs_actual(
                year,
                month,
                indicator,
                entity_id,
            )
            self.view.show_result(result)
        except (TargetDomainError, SQLAlchemyError, RuntimeError) as error:
            self._rollback_local()
            self.view.set_status(
                f"Falha ao carregar Meta x Realizado: {error}",
                error=True,
            )

        if self.ranking is not None:
            try:
                year = self.view.ranking_year.value()
                quarter = self.view.ranking_quarter.currentData()
                rows = self.ranking.quarterly(year, quarter)
                annual = self.ranking.annual(year)
                self.view.show_ranking(rows, annual)
            except (ValueError, SQLAlchemyError, RuntimeError) as error:
                self._rollback_local(self.ranking)
                self.view.set_status(
                    f"Falha ao carregar Ranking: {error}",
                    error=True,
                )

    def select_import_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self.view,
            "Selecionar arquivo de Metas",
            "",
            "Planilhas Excel (*.xlsx *.xlsm)",
        )

        if not path:
            return

        self.selected_import_file_path = path
        self.import_file_path = None

        self.view.import_summary.setText(
            f"Arquivo selecionado: {Path(path).name}"
        )
        self.view.import_issues.setText("")
        self.view.validate_import_button.setEnabled(True)
        self.view.confirm_import_button.setEnabled(False)
        self.view.set_status("Arquivo selecionado. Clique em Validar.")

    def validate_selected_import_file(self) -> None:
        if not self.selected_import_file_path:
            return

        self.validate_import_file(self.selected_import_file_path)

    def validate_import_file(self, path: str) -> None:
        self.import_file_path = None
        self.view.validate_import_button.setEnabled(False)
        self.view.confirm_import_button.setEnabled(False)

        def succeeded(validation: dict) -> None:
            self.view.show_import_validation(validation)
            self.view.validate_import_button.setEnabled(True)

            if validation.get("can_import"):
                self.import_file_path = path
                self.view.confirm_import_button.setEnabled(True)

        def failed(error: Exception) -> None:
            self.view.set_status(
                f"Falha ao validar arquivo de Metas: {error}",
                error=True,
            )
            self.view.validate_import_button.setEnabled(
                self.selected_import_file_path is not None
            )

        self._run_operation(
            service=self.service,
            window_title="Valida\u00e7\u00e3o de Metas",
            operation=lambda: self.service.validate_import(path),
            succeeded=succeeded,
            failed=failed,
        )

    def import_validated_file(self) -> None:
        if not self.import_file_path or (
            self._import_thread is not None
            and self._import_thread.isRunning()
        ):
            return

        selected_file = self.import_file_path
        filters = self.view.selected_filters()
        ranking_year = self.view.ranking_year.value()
        ranking_quarter = self.view.ranking_quarter.currentData()

        self.view.confirm_import_button.setEnabled(False)
        self.view.validate_import_button.setEnabled(False)
        self.view.import_file_button.setEnabled(False)

        def operation():
            import_result = self.service.import_file(selected_file)

            entities = self.service.list_entities()
            target_result = self._get_target_vs_actual(
                *filters
            )

            ranking_payload = None
            if self.ranking is not None:
                ranking_payload = (
                    self.ranking.quarterly(
                        ranking_year,
                        ranking_quarter,
                    ),
                    self.ranking.annual(ranking_year),
                )

            return (
                import_result,
                entities,
                target_result,
                ranking_payload,
            )

        def succeeded(payload) -> None:
            (
                import_result,
                entities,
                target_result,
                ranking_payload,
            ) = payload

            self.view.show_import_result(import_result)
            self.import_file_path = None
            self.selected_import_file_path = None

            self.view.set_entities(entities)
            self.view.show_result(target_result)

            if ranking_payload is not None:
                rows, annual = ranking_payload
                self.view.show_ranking(rows, annual)

            self.view.import_file_button.setEnabled(True)
            self.view.validate_import_button.setEnabled(False)
            self.view.confirm_import_button.setEnabled(False)

        def failed(error: Exception) -> None:
            if isinstance(error, APIReadTimeoutError):
                self.import_file_path = None

            self.view.set_status(
                f"Falha ao importar Metas: {error}",
                error=True,
            )

            self.view.import_file_button.setEnabled(True)
            self.view.validate_import_button.setEnabled(
                self.selected_import_file_path is not None
            )
            self.view.confirm_import_button.setEnabled(
                self.import_file_path is not None
            )

        self._run_operation(
            service=self.service,
            window_title="Importa\u00e7\u00e3o de Metas",
            operation=operation,
            succeeded=succeeded,
            failed=failed,
            force_worker=True,
            import_operation=True,
            dialog_factory=lambda: TargetImportProgressDialog(
                self.view
            ),
        )

    def refresh_ranking(self) -> None:
        if self.ranking is None:
            return

        year = self.view.ranking_year.value()
        quarter = self.view.ranking_quarter.currentData()

        def operation():
            return (
                self.ranking.quarterly(year, quarter),
                self.ranking.annual(year),
            )

        def succeeded(payload) -> None:
            rows, annual = payload
            self.view.show_ranking(rows, annual)

        def failed(error: Exception) -> None:
            self._rollback_local(self.ranking)
            self.view.set_status(
                f"Falha ao carregar Ranking: {error}",
                error=True,
            )

        self._run_operation(
            service=self.ranking,
            window_title="Ranking",
            operation=operation,
            succeeded=succeeded,
            failed=failed,
        )

    def refresh_entities(self) -> None:
        def succeeded(entities) -> None:
            self.view.set_entities(entities)

        def failed(_error: Exception) -> None:
            self._rollback_local()
            self.view.set_entities([])

        self._run_operation(
            service=self.service,
            window_title="Entidades",
            operation=self.service.list_entities,
            succeeded=succeeded,
            failed=failed,
        )

    def _get_target_vs_actual(self, year, month, indicator, entity_id):
        if indicator != "TODAS":
            return self.service.get_target_vs_actual(
                year,
                month,
                indicator,
                entity_id,
            )

        queries = self.service.get_target_vs_actual(
            year,
            month,
            "CONSULTAS",
            entity_id,
        )
        registrations = self.service.get_target_vs_actual(
            year,
            month,
            "REGISTROS",
            entity_id,
        )

        comparisons = tuple(queries.comparisons) + tuple(
            registrations.comparisons
        )

        zero = Decimal("0.0000")
        target_total = sum(
            (item.target for item in comparisons),
            zero,
        )
        actual_total = sum(
            (item.actual for item in comparisons),
            zero,
        )
        difference_total = actual_total - target_total

        achievement = (
            None
            if target_total == 0
            else (
                actual_total
                / target_total
                * Decimal("100")
            ).quantize(Decimal("0.0001"))
        )

        summary = type(queries.summary)(
            len({item.entity_code for item in comparisons}),
            target_total,
            actual_total,
            difference_total,
            achievement,
        )

        return type(queries)(
            comparisons,
            summary,
        )

    def refresh(self) -> None:
        filters = self.view.selected_filters()

        def succeeded(result) -> None:
            self.view.show_result(result)

        def failed(error: Exception) -> None:
            self._rollback_local()
            self.view.set_status(
                f"Falha ao carregar Meta x Realizado: {error}",
                error=True,
            )

        self._run_operation(
            service=self.service,
            window_title="Metas",
            operation=lambda: self._get_target_vs_actual(
                *filters
            ),
            succeeded=succeeded,
            failed=failed,
        )

    def open_new_dialog(self) -> None:
        def loaded(entities) -> None:
            if not entities:
                self.view.set_status(
                    "N\u00e3o h\u00e1 Entidades dispon\u00edveis para cadastro.",
                    error=True,
                )
                return

            dialog = TargetDialog(entities, self.view)

            year, month, indicator, entity_id = (
                self.view.selected_filters()
            )

            dialog.year.setValue(year)
            dialog.month.set_month(month)
            dialog.indicator.setCurrentIndex(
                dialog.indicator.findData(indicator)
            )

            if entity_id is not None:
                dialog.entity.setCurrentIndex(
                    dialog.entity.findData(entity_id)
                )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            self._create_target(dialog.create_values())

        def failed(error: Exception) -> None:
            self.view.set_status(
                f"Falha ao carregar Entidades: {error}",
                error=True,
            )

        self._run_operation(
            service=self.service,
            window_title="Nova Meta",
            operation=self.service.list_entities,
            succeeded=loaded,
            failed=failed,
        )

    def _create_target(self, values) -> None:
        (
            year,
            month,
            entity_id,
            indicator,
            target,
            actual,
            notes,
        ) = values

        selected_filters = self.view.selected_filters()

        def operation():
            self.service.create_target(
                entity_id=entity_id,
                year=year,
                month=month,
                indicator=indicator,
                target_value=target,
                actual_value=actual,
                notes=notes,
            )

            return self._get_target_vs_actual(
                *selected_filters
            )

        def succeeded(result) -> None:
            self.view.show_result(result)
            self.view.set_status(
                "Meta cadastrada com sucesso."
            )

        def failed(error: Exception) -> None:
            self.view.set_status(
                str(error),
                error=True,
            )

        self._run_operation(
            service=self.service,
            window_title="Salvando Meta",
            operation=operation,
            succeeded=succeeded,
            failed=failed,
        )

    def open_edit_dialog(self) -> None:
        target_id = self.view.selected_target_id()

        if target_id is None:
            self.view.set_status(
                "Selecione uma Meta para editar.",
                error=True,
            )
            return

        def operation():
            return (
                self.service.get_target(target_id),
                self.service.list_entities(),
            )

        def loaded(payload) -> None:
            target, entities = payload

            if target is None:
                self.view.set_status(
                    "Meta n\u00e3o encontrada.",
                    error=True,
                )
                return

            dialog = TargetDialog(
                entities,
                self.view,
                target,
            )

            if dialog.exec() != QDialog.DialogCode.Accepted:
                return

            self._update_target(
                target.id,
                dialog.update_values(),
            )

        def failed(error: Exception) -> None:
            self.view.set_status(
                f"Falha ao carregar Meta: {error}",
                error=True,
            )

        self._run_operation(
            service=self.service,
            window_title="Editar Meta",
            operation=operation,
            succeeded=loaded,
            failed=failed,
        )

    def _update_target(self, target_id: int, values) -> None:
        value, notes = values
        selected_filters = self.view.selected_filters()

        def operation():
            self.service.update_target(
                target_id,
                target_value=value,
                notes=notes,
            )

            return self._get_target_vs_actual(
                *selected_filters
            )

        def succeeded(result) -> None:
            self.view.show_result(result)
            self.view.set_status(
                "Meta atualizada com sucesso."
            )

        def failed(error: Exception) -> None:
            self.view.set_status(
                str(error),
                error=True,
            )

        self._run_operation(
            service=self.service,
            window_title="Atualizando Meta",
            operation=operation,
            succeeded=succeeded,
            failed=failed,
        )
