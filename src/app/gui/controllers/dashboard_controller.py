from PySide6.QtCore import QObject, QThread, Slot
from sqlalchemy.exc import SQLAlchemyError

from app.gui.pages.dashboard import DashboardPage
from app.gui.processing import OperationWorker, ProcessingDialog
from app.services.dashboard_service import DashboardService


class DashboardController(QObject):
    def __init__(self, view: DashboardPage, service: DashboardService) -> None:
        super().__init__(view)
        self.view = view
        self.service = service

        self._refresh_thread: QThread | None = None
        self._refresh_worker: OperationWorker | None = None
        self._refresh_dialog: ProcessingDialog | None = None
        self._requested_period: tuple[int, int] | None = None
        self._years_thread: QThread | None = None
        self._years_worker: OperationWorker | None = None
        self._years_loaded = False
        self._refresh_after_years = False
        self._years_retry_on_finish = False

        self.view.refresh_button.clicked.connect(self.refresh)
        self.view.boe_refresh_button.clicked.connect(self.refresh)
        self.view.target_refresh_button.clicked.connect(self.refresh)
        self._start_available_years_load()

    def _start_available_years_load(self) -> None:
        if self._years_thread is not None and self._years_thread.isRunning():
            return

        loader = getattr(self.service, "get_available_years", None)
        if loader is None:
            self._years_loaded = True
            if self._refresh_after_years:
                self._refresh_after_years = False
                self.refresh()
            return

        self._years_thread = QThread(self)
        self._years_worker = OperationWorker(loader)
        self._years_worker.moveToThread(self._years_thread)

        self._years_thread.started.connect(self._years_worker.run)
        self._years_worker.succeeded.connect(self._years_succeeded)
        self._years_worker.failed.connect(self._years_failed)
        self._years_worker.finished.connect(self._years_thread.quit)
        self._years_worker.finished.connect(self._years_worker.deleteLater)
        self._years_thread.finished.connect(self._years_finished)

        self._years_thread.start()

    @Slot(object)
    def _years_succeeded(self, years: object) -> None:
        if not isinstance(years, dict):
            self.view.set_status(
                "Falha ao carregar anos disponíveis: resposta inválida.",
                error=True,
            )
            return

        self.view.set_available_years(
            years.get("financial_years", []),
            years.get("boe_years", []),
            years.get("target_years", []),
        )
        self._years_loaded = True

    @Slot(object)
    def _years_failed(self, error: Exception) -> None:
        self.view.set_status(
            f"Falha ao carregar anos disponíveis: {error}",
            error=True,
        )

    @Slot()
    def _years_finished(self) -> None:
        if self._years_thread is not None:
            self._years_thread.deleteLater()
        self._years_thread = None
        self._years_worker = None

        if self._refresh_after_years and self._years_loaded:
            self._refresh_after_years = False
            self._years_retry_on_finish = False
            self.refresh()
            return

        if (
            self._refresh_after_years
            and not self._years_loaded
            and self._years_retry_on_finish
        ):
            self._years_retry_on_finish = False
            self._start_available_years_load()

    def refresh(self) -> None:
        if (
            self._refresh_thread is not None
            and self._refresh_thread.isRunning()
        ):
            self.view.set_status(
                "Processando Dashboard... Aguarde a conclusão da atualização atual."
            )
            return

        if not self._years_loaded:
            self._refresh_after_years = True
            self.view.set_status("Carregando períodos disponíveis...")
            if self._years_thread is not None and self._years_thread.isRunning():
                self._years_retry_on_finish = True
            else:
                self._start_available_years_load()
            return

        year, month = self.view.selected_period()
        filters = self.view.selected_dashboard_filters()

        self._requested_period = (year, month)
        self.view.refresh_button.setEnabled(False)
        self.view.boe_refresh_button.setEnabled(False)
        self.view.target_refresh_button.setEnabled(False)
        self.view.set_status(
            f"Processando Dashboard para {month:02d}/{year}..."
        )

        if self.view.isVisible():
            self._refresh_dialog = ProcessingDialog(
                self.view,
                window_title="Dashboard",
                title="Atualizando Dashboard...",
                description=(
                    f"Carregando informações de {month:02d}/{year}. "
                    "Aguarde..."
                ),
            )
            self._refresh_dialog.show()

        self._refresh_thread = QThread(self)

        def load_dashboard() -> tuple[str, object]:
            if hasattr(self.service, "get_dashboard_data"):
                return (
                    "dashboard",
                    self.service.get_dashboard_data(
                        year,
                        month,
                        **filters,
                    ),
                )

            return (
                "summary",
                self.service.get_dashboard_summary(year, month),
            )

        self._refresh_worker = OperationWorker(load_dashboard)
        self._refresh_worker.moveToThread(self._refresh_thread)

        self._refresh_thread.started.connect(
            self._refresh_worker.run
        )
        self._refresh_worker.succeeded.connect(
            self._refresh_succeeded
        )
        self._refresh_worker.failed.connect(
            self._refresh_failed
        )
        self._refresh_worker.finished.connect(
            self._refresh_thread.quit
        )
        self._refresh_worker.finished.connect(
            self._refresh_worker.deleteLater
        )
        self._refresh_thread.finished.connect(
            self._refresh_finished
        )

        self._refresh_thread.start()

    @Slot(object)
    def _refresh_succeeded(self, result: object) -> None:
        result_type, data = result

        if result_type == "dashboard":
            self.view.show_dashboard_data(data)
        else:
            self.view.show_summary(data)

        if self._requested_period is not None:
            year, month = self._requested_period
            self.view.set_status(
                f"Dashboard atualizado para {month:02d}/{year}."
            )

    @Slot(object)
    def _refresh_failed(self, error: Exception) -> None:
        if isinstance(error, SQLAlchemyError) and hasattr(
            self.service,
            "boe",
        ):
            self.service.boe.repository.session.rollback()

        self.view.set_status(
            f"Falha ao carregar Dashboard: {error}",
            error=True,
        )

    @Slot()
    def _refresh_finished(self) -> None:
        if self._refresh_dialog is not None:
            self._refresh_dialog.accept()
            self._refresh_dialog.deleteLater()
            self._refresh_dialog = None

        if self._refresh_thread is not None:
            self._refresh_thread.deleteLater()

        self._refresh_thread = None
        self._refresh_worker = None
        self.view.refresh_button.setEnabled(True)
        self.view.boe_refresh_button.setEnabled(True)
        self.view.target_refresh_button.setEnabled(True)
