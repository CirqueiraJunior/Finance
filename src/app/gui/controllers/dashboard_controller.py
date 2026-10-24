from weakref import ref

from PySide6.QtCore import QObject, QThread, QTimer, Slot
from shiboken6 import isValid
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
        self._pending_refresh_areas: set[str] | None = None
        self._refresh_active = False
        self._request_finished = False
        self._render_in_progress = False
        self._entities_thread: QThread | None = None
        self._entities_worker: OperationWorker | None = None
        self._entity_request_generation = 0
        self._active_entity_generation = 0
        self._pending_entity_areas: set[str] = set()

        self.view.refresh_button.clicked.connect(
            lambda _checked=False: self.refresh({"financial"})
        )
        self.view.boe_refresh_button.clicked.connect(
            lambda _checked=False: self.refresh({"boe"})
        )
        self.view.target_refresh_button.clicked.connect(
            lambda _checked=False: self.refresh({"targets"})
        )
        self.view.target_region_filter.currentIndexChanged.connect(
            lambda _index: self.refresh_entity_options({"targets"})
        )
        self._start_available_years_load()
        self.refresh_entity_options({"boe", "targets"})

    def refresh_entity_options(self, areas: set[str] | None = None) -> None:
        loader = getattr(self.service, "get_dashboard_entity_options", None)
        if loader is None:
            return
        requested = set(areas or {"boe", "targets"}) & {"boe", "targets"}
        if not requested:
            return

        self._entity_request_generation += 1
        generation = self._entity_request_generation
        if (
            self._entities_thread is not None
            and self._entities_thread.isRunning()
        ):
            self._pending_entity_areas.update(requested)
            return

        self._start_entity_options_load(requested, generation)

    def _start_entity_options_load(
        self, areas: set[str], generation: int
    ) -> None:
        loader = self.service.get_dashboard_entity_options
        region = (
            self.view.target_region_filter.currentData()
            if "targets" in areas else None
        )
        self._active_entity_generation = generation
        self._entities_thread = QThread(self)

        def load_options():
            return generation, loader(areas=areas, region=region)

        self._entities_worker = OperationWorker(load_options)
        self._entities_worker.moveToThread(self._entities_thread)
        self._entities_thread.started.connect(self._entities_worker.run)
        self._entities_worker.succeeded.connect(self._entities_succeeded)
        self._entities_worker.failed.connect(self._entities_failed)
        self._entities_worker.finished.connect(self._entities_thread.quit)
        self._entities_worker.finished.connect(
            self._entities_worker.deleteLater
        )
        self._entities_thread.finished.connect(self._entities_finished)
        self._entities_thread.start()

    @Slot(object)
    def _entities_succeeded(self, result: object) -> None:
        generation, options = result
        if generation != self._entity_request_generation:
            return
        if not isinstance(options, dict):
            self.view.set_status(
                "Falha ao carregar entidades do Dashboard: resposta inválida.",
                error=True,
            )
            return
        self.view.set_dashboard_entity_options(options)

    @Slot(object)
    def _entities_failed(self, error: Exception) -> None:
        if self._active_entity_generation != self._entity_request_generation:
            return
        self.view.set_status(
            f"Falha ao carregar entidades do Dashboard: {error}",
            error=True,
        )

    @Slot()
    def _entities_finished(self) -> None:
        if self._entities_thread is not None:
            self._entities_thread.deleteLater()
        self._entities_thread = None
        self._entities_worker = None
        if self._pending_entity_areas:
            pending = set(self._pending_entity_areas)
            self._pending_entity_areas.clear()
            self._start_entity_options_load(
                pending, self._entity_request_generation
            )

    def _start_available_years_load(self) -> None:
        if self._years_thread is not None and self._years_thread.isRunning():
            return

        loader = getattr(self.service, "get_available_years", None)
        if loader is None:
            self._years_loaded = True
            if self._refresh_after_years:
                self._refresh_after_years = False
                pending_areas = self._pending_refresh_areas
                self._pending_refresh_areas = None
                self.refresh(pending_areas)
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
            pending_areas = self._pending_refresh_areas
            self._pending_refresh_areas = None
            QTimer.singleShot(
                0,
                lambda areas=pending_areas: self.refresh(areas),
            )
            return

        if (
            self._refresh_after_years
            and not self._years_loaded
            and self._years_retry_on_finish
        ):
            self._years_retry_on_finish = False
            QTimer.singleShot(
                0,
                self._start_available_years_load,
            )

    def refresh(self, areas: set[str] | None = None) -> None:
        if self._refresh_active:
            self.view.set_status(
                "Processando Dashboard... Aguarde a conclusão da atualização atual."
            )
            return

        if not self._years_loaded:
            self._refresh_after_years = True
            self._pending_refresh_areas = areas
            self.view.set_status("Carregando períodos disponíveis...")
            if self._years_thread is not None and self._years_thread.isRunning():
                self._years_retry_on_finish = True
            else:
                self._start_available_years_load()
            return

        year, month = self.view.selected_period()
        try:
            filters = self.view.selected_dashboard_filters(areas=areas)
        except ValueError as error:
            self.view.set_status(str(error), error=True)
            return

        self._requested_period = (year, month)
        self._refresh_active = True
        self._request_finished = False
        self._render_in_progress = False
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
                        areas=areas,
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
            self._render_in_progress = True
            controller_ref = ref(self)

            def render_finished() -> None:
                controller = controller_ref()
                if controller is not None and isValid(controller):
                    controller._render_finished()

            def render_failed(error: Exception) -> None:
                controller = controller_ref()
                if controller is not None and isValid(controller):
                    controller._render_failed(error)

            try:
                self.view.show_dashboard_data_async(
                    data, render_finished, render_failed
                )
            except Exception as error:
                self._render_failed(error)
        else:
            self.view.show_summary(data)
            self._set_success_status()

    def _render_finished(self) -> None:
        if not self._render_in_progress:
            return
        self._render_in_progress = False
        self._set_success_status()
        if self._request_finished:
            self._finalize_refresh()

    def _render_failed(self, error: Exception) -> None:
        self._render_in_progress = False
        self._refresh_failed(error)
        if self._request_finished:
            self._finalize_refresh()

    def _set_success_status(self) -> None:
        if self._requested_period is None:
            return
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
        self._request_finished = True
        if self._render_in_progress:
            return
        self._finalize_refresh()

    def _finalize_refresh(self) -> None:
        if not self._refresh_active:
            return
        if self._refresh_dialog is not None:
            self._refresh_dialog.accept()
            self._refresh_dialog.deleteLater()
            self._refresh_dialog = None

        if self._refresh_thread is not None:
            self._refresh_thread.deleteLater()

        self._refresh_thread = None
        self._refresh_worker = None
        self._refresh_active = False
        self._request_finished = False
        self._render_in_progress = False
        self.view.refresh_button.setEnabled(True)
        self.view.boe_refresh_button.setEnabled(True)
        self.view.target_refresh_button.setEnabled(True)
