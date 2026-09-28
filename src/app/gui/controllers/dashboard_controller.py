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
        self._refresh_pending = False
        self._requested_period: tuple[int, int] | None = None

        self.view.refresh_button.clicked.connect(self.refresh)
        self.view.year_filter.valueChanged.connect(self.refresh)
        self.view.month_filter.currentIndexChanged.connect(self.refresh)

        for widget in self.view.dashboard_filters():
            widget.currentIndexChanged.connect(self.refresh)

    def refresh(self) -> None:
        if (
            self._refresh_thread is not None
            and self._refresh_thread.isRunning()
        ):
            self._refresh_pending = True
            self.view.set_status(
                "Processando Dashboard... Uma nova atualização será aplicada em seguida."
            )
            return

        year, month = self.view.selected_period()
        filters = self.view.selected_dashboard_filters()

        self._requested_period = (year, month)
        self.view.refresh_button.setEnabled(False)
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

        if self._refresh_pending:
            self._refresh_pending = False
            self.refresh()