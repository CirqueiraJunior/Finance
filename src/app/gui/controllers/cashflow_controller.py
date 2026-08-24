from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import CashflowDomainError
from app.gui.pages.financeiro import CashflowEntryDialog, FinanceiroPage
from app.models.cashflow_entry import CashflowType
from app.services.cashflow_service import CashflowService


class CashflowController(QObject):
    def __init__(self, view: FinanceiroPage, service: CashflowService) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self.view.filter_button.clicked.connect(self.refresh_entries)
        self.view.new_entry_button.clicked.connect(self.open_new_entry_dialog)
        self.refresh_entries()

    def refresh_entries(self) -> None:
        year, month = self.view.selected_period()
        try:
            entries = self.service.list_entries_by_period(year, month)
            self.view.show_entries(
                entries, self.service.get_monthly_summary(year, month)
            )
        except (CashflowDomainError, SQLAlchemyError) as error:
            self.service.repository.session.rollback()
            self.view.show_entries([])
            self.view.set_status(f"Falha ao carregar lançamentos: {error}", error=True)

    def open_new_entry_dialog(self) -> None:
        dialog = CashflowEntryDialog(self.view)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        entry_type, entry_date, description, category, value, notes = dialog.values()
        year, month = self.view.selected_period()
        try:
            if entry_type == CashflowType.REVENUE.value:
                self.service.create_indirect_revenue(
                    year=year, month=month, entry_date=entry_date,
                    description=description, value=value, notes=notes,
                )
                message = "Receita Indireta cadastrada com sucesso."
            else:
                self.service.create_expense(
                    year=year, month=month, entry_date=entry_date,
                    description=description, category=category,
                    value=value, notes=notes,
                )
                message = "Despesa cadastrada com sucesso."
        except CashflowDomainError as error:
            self.view.set_status(str(error), error=True)
            return
        self.view.set_status(message)
        self.refresh_entries()

    def open_indirect_revenue_dialog(self) -> None:
        self.open_new_entry_dialog()
