from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import CashflowDomainError, InvestmentDomainError
from app.gui.pages.financeiro import CashflowEntryDialog, FinanceiroPage
from app.models.cashflow_entry import CashflowType
from app.models.investment_movement import InvestmentMovementType
from app.repositories.cashflow_catalog_repository import CashflowCatalogRepository
from app.repositories.investment_repository import InvestmentRepository
from app.services.cashflow_catalog_service import CashflowCatalogService
from app.services.cashflow_service import CashflowService
from app.services.financial_flow_service import FinancialFlowService
from app.services.investment_service import InvestmentService


class CashflowController(QObject):
    def __init__(
        self, view: FinanceiroPage, service: CashflowService,
        investment_service: InvestmentService | None = None,
        financial_flow=None,
        catalog_service=None,
    ) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self.investment_service = investment_service or InvestmentService(
            InvestmentRepository(service.repository.session)
        )
        self.financial_flow = financial_flow or FinancialFlowService(service, self.investment_service)
        self.catalog_service = catalog_service or CashflowCatalogService(
            CashflowCatalogRepository(service.repository.session)
        )
        self.view.filter_button.clicked.connect(self.refresh_entries)
        self.view.new_entry_button.clicked.connect(self.open_new_entry_dialog)
        self.refresh_entries()

    def refresh_entries(self) -> None:
        year, month = self.view.selected_period()
        try:
            self.view.show_financial_flow(
                self.financial_flow.list_by_period(year, month),
                self.financial_flow.get_summary(year, month),
            )
        except (CashflowDomainError, InvestmentDomainError, SQLAlchemyError, RuntimeError) as error:
            self.service.repository.session.rollback()
            self.view.set_status(f"Falha ao carregar lançamentos: {error}", error=True)

    def open_new_entry_dialog(self) -> None:
        year, month = self.view.selected_period()
        dialog = CashflowEntryDialog(
            self.view,
            self.catalog_service.list_options(),
            period_year=year,
            period_month=month,
        )

        def update_balance() -> None:
            dialog.set_available_balance(
                self.investment_service.get_applied_balance(dialog.movement_date())
            )

        dialog.category.currentIndexChanged.connect(update_balance)
        dialog.year_input.valueChanged.connect(update_balance)
        dialog.month_input.currentIndexChanged.connect(update_balance)
        update_balance()
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        entry_type, entry_date, description, category, value, notes, boe = dialog.values()
        year, month = entry_date.year, entry_date.month
        try:
            if entry_type == CashflowType.REVENUE.value:
                self.service.create_indirect_revenue(
                    year=year, month=month, entry_date=entry_date,
                    description=description, value=value, notes=notes, boe=boe,
                )
                message = "Receita Indireta cadastrada com sucesso."
            elif entry_type == CashflowType.EXPENSE.value:
                self.service.create_expense(
                    year=year, month=month, entry_date=entry_date,
                    description=description, category=category,
                    value=value, notes=notes, boe=boe,
                )
                message = "Despesa cadastrada com sucesso."
            elif entry_type == InvestmentMovementType.APPLICATION.value:
                self.financial_flow.create_application(
                    movement_date=entry_date, description=description,
                    value=value, notes=notes,
                )
                message = "Aplicação cadastrada com sucesso."
            else:
                self.financial_flow.create_redemption(
                    movement_date=entry_date, description=description,
                    value=value, notes=notes,
                )
                message = "Resgate cadastrado com sucesso."
        except (CashflowDomainError, InvestmentDomainError, RuntimeError) as error:
            self.view.set_status(str(error), error=True)
            return
        self.view.set_status(message)
        self.refresh_entries()

    def open_indirect_revenue_dialog(self) -> None:
        self.open_new_entry_dialog()
