from PySide6.QtCore import QObject, QThread
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import CSVExportValidationError
from app.gui.pages.relatorios import RelatoriosPage
from app.gui.processing import OperationWorker, ProcessingDialog
from app.services.report_service import ReportService
from app.services.site_csv_service import SiteCSVService
from app.api_client import APIClient


class ReportController(QObject):
    def __init__(
        self,
        view: RelatoriosPage,
        report_service: ReportService,
        csv_service: SiteCSVService,
    ) -> None:
        super().__init__(view)
        self.view = view
        self.report_service = report_service
        self.csv_service = csv_service

        self._operation_thread: QThread | None = None
        self._operation_worker: OperationWorker | None = None
        self._operation_dialog: ProcessingDialog | None = None

        self.view.refresh_button.clicked.connect(self.refresh)
        self.view.choose_folder_button.clicked.connect(
            self.view.choose_destination
        )
        self.view.validate_button.clicked.connect(self.validate_csv)
        self.view.export_button.clicked.connect(self.export_csv)

        self.refresh()

    @staticmethod
    def _is_remote(service) -> bool:
        return isinstance(getattr(service, "api", None), APIClient)

    def _run_operation(
        self,
        *,
        service,
        window_title: str,
        operation,
        succeeded,
        failed,
    ) -> None:
        # Serviços locais usam Session SQLAlchemy criada na thread
        # principal. Apenas serviços remotos/API vão para QThread.
        if not self._is_remote(service):
            try:
                succeeded(operation())
            except Exception as error:
                failed(error)
            return

        if (
            self._operation_thread is not None
            and self._operation_thread.isRunning()
        ):
            return

        dialog = ProcessingDialog(
            self.view,
            window_title=window_title,
        )
        thread = QThread(self)
        worker = OperationWorker(operation)
        worker.moveToThread(thread)

        self._operation_dialog = dialog
        self._operation_thread = thread
        self._operation_worker = worker

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

    def refresh(self) -> None:
        year = self.view.selected_year()

        def succeeded(report) -> None:
            self.view.show_report(report)
            self.view.set_status(
                "Relat\u00f3rio anual atualizado."
            )

        def failed(error: Exception) -> None:
            self._rollback()
            self.view.set_status(
                f"Falha ao carregar relat\u00f3rio: {error}",
                error=True,
            )

        self._run_operation(
            service=self.report_service,
            window_title="Relat\u00f3rio Anual",
            operation=lambda: self.report_service.get_annual_report(
                year
            ),
            succeeded=succeeded,
            failed=failed,
        )

    def validate_csv(self) -> None:
        year = self.view.selected_year()

        def succeeded(result) -> None:
            lines = [
                f"Ano: {result.year}",
                (
                    "Status: APROVADO"
                    if result.valid
                    else "Status: BLOQUEADO"
                ),
                f"Entidades: {result.entity_count}",
                (
                    "Meta/Realizado: "
                    f"{result.target_rows} registros"
                ),
                (
                    "Associa\u00e7\u00e3o: "
                    f"{result.association_rows} registros"
                ),
            ]

            if result.errors:
                lines.extend(
                    [
                        "",
                        "Primeiras inconsist\u00eancias:",
                        *result.errors[:12],
                    ]
                )

                if len(result.errors) > 12:
                    lines.append(
                        "... e mais "
                        f"{len(result.errors) - 12} "
                        "inconsist\u00eancias."
                    )

            self.view.show_export_message(
                "\n".join(lines)
            )

            self.view.set_status(
                (
                    "Valida\u00e7\u00e3o conclu\u00edda."
                    if result.valid
                    else (
                        "Exporta\u00e7\u00e3o bloqueada por "
                        "inconsist\u00eancias."
                    )
                ),
                error=not result.valid,
            )

        def failed(error: Exception) -> None:
            self._rollback()
            self.view.set_status(
                f"Falha na valida\u00e7\u00e3o: {error}",
                error=True,
            )

        self._run_operation(
            service=self.csv_service,
            window_title="Valida\u00e7\u00e3o CSV",
            operation=lambda: self.csv_service.validate_period(
                year
            ),
            succeeded=succeeded,
            failed=failed,
        )

    def export_csv(self) -> None:
        destination = self.view.destination()

        if destination is None:
            self.view.set_status(
                "Selecione a pasta de exporta\u00e7\u00e3o.",
                error=True,
            )
            return

        year = self.view.selected_year()

        def succeeded(result) -> None:
            self.view.show_export_message(
                "Exporta\u00e7\u00e3o conclu\u00edda:\n"
                + "\n".join(
                    path.name for path in result.files
                )
                + (
                    "\n\nRelat\u00f3rio: "
                    f"{result.report_file.name}"
                )
            )

            self.view.set_status(
                "Cinco CSVs gerados com sucesso."
            )

        def failed(error: Exception) -> None:
            if isinstance(
                error,
                CSVExportValidationError,
            ):
                self.view.show_export_message(
                    "Exporta\u00e7\u00e3o bloqueada.\n\n"
                    + "\n".join(error.errors[:15])
                )
                self.view.set_status(
                    (
                        "Corrija as inconsist\u00eancias "
                        "antes de exportar."
                    ),
                    error=True,
                )
                return

            self._rollback()
            self.view.set_status(
                f"Falha ao exportar: {error}",
                error=True,
            )

        self._run_operation(
            service=self.csv_service,
            window_title="Exporta\u00e7\u00e3o CSV",
            operation=lambda: self.csv_service.export_all(
                year,
                destination,
            ),
            succeeded=succeeded,
            failed=failed,
        )

    def _rollback(self) -> None:
        repository = getattr(
            self.csv_service,
            "export_repository",
            None,
        )
        session = getattr(
            repository,
            "session",
            None,
        )

        if session is not None:
            try:
                session.rollback()
            except Exception:
                pass
