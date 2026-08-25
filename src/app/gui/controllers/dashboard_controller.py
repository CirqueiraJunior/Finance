from PySide6.QtCore import QObject
from sqlalchemy.exc import SQLAlchemyError

from app.gui.pages.dashboard import DashboardPage
from app.services.dashboard_service import DashboardService


class DashboardController(QObject):
    def __init__(self, view: DashboardPage, service: DashboardService) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self.view.refresh_button.clicked.connect(self.refresh)
        self.view.year_filter.valueChanged.connect(self.refresh)
        self.view.month_filter.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        year, month = self.view.selected_period()
        try:
            self.view.show_summary(
                self.service.get_dashboard_summary(year, month)
            )
            self.view.set_status(f"Dashboard atualizado para {month:02d}/{year}.")
        except SQLAlchemyError as error:
            self.service.boe.repository.session.rollback()
            self.view.set_status(f"Falha ao carregar Dashboard: {error}", error=True)
