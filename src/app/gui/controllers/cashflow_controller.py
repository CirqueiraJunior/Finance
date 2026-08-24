from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import CashflowDomainError
from app.gui.pages.financeiro import FinanceiroPage, IndirectRevenueDialog
from app.services.cashflow_service import CashflowService


class CashflowController(QObject):
    def __init__(self, view: FinanceiroPage, service: CashflowService) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self.view.filter_button.clicked.connect(self.refresh_entries)
        self.view.new_indirect_button.clicked.connect(self.open_indirect_revenue_dialog)
        self.refresh_entries()

    def refresh_entries(self) -> None:
        year, month = self.view.selected_period()
        try:
            self.view.show_entries(self.service.list_entries_by_period(year, month))
        except (CashflowDomainError, SQLAlchemyError) as error:
            self.service.repository.session.rollback()
            self.view.show_entries([])
            self.view.set_status(f"Falha ao carregar lançamentos: {error}", error=True)

    def open_indirect_revenue_dialog(self) -> None:
        dialog = IndirectRevenueDialog(self.view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        entry_date, description, value, notes = dialog.values()
        year, month = self.view.selected_period()
        try:
            self.service.create_indirect_revenue(
                year=year,
                month=month,
                entry_date=entry_date,
                description=description,
                value=value,
                notes=notes,
            )
        except CashflowDomainError as error:
            self.view.set_status(str(error), error=True)
            return
        self.view.set_status("Receita Indireta cadastrada com sucesso.")
        self.refresh_entries()
