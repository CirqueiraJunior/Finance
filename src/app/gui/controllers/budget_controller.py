from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog
from sqlalchemy.exc import SQLAlchemyError

from app.core.exceptions import BudgetDomainError
from app.gui.pages.orcamento import BudgetDialog, OrcamentoPage
from app.services.budget_service import BudgetService


class BudgetController(QObject):
    def __init__(self, view: OrcamentoPage, service: BudgetService,
                 catalog_service=None) -> None:
        super().__init__(view)
        self.view = view
        self.service = service
        self.catalog_service = catalog_service
        self.view.filter_button.clicked.connect(self.refresh)
        self.view.new_button.clicked.connect(self.open_new_dialog)
        self.view.edit_button.clicked.connect(self.open_edit_dialog)
        self.refresh()

    def refresh(self) -> None:
        year, month = self.view.selected_period()
        try:
            result = self.service.get_budget_vs_actual(year, month)
            budgets = (
                self.service.list_by_year(year)
                if month is None else self.service.list_by_period(year, month)
            )
            self.view.show_result(result, budgets)
        except (BudgetDomainError, SQLAlchemyError, RuntimeError) as error:
            self.service.repository.session.rollback()
            self.view.set_status(f"Falha ao carregar orçamento: {error}", error=True)

    def open_new_dialog(self) -> None:
        try:
            options = self.catalog_service.list_budget_options() if self.catalog_service else ()
        except RuntimeError as error:
            self.view.set_status(f"Falha ao carregar Catálogo: {error}", error=True)
            return
        dialog = BudgetDialog(self.view, catalog_options=options)
        year, month = self.view.selected_period()
        dialog.year.setValue(year)
        if month is not None:
            dialog.month.set_month(month)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        year, month, entry_type, category, description, value, notes = dialog.create_values()
        try:
            self.service.create_budget(
                year=year, month=month, entry_type=entry_type, category=category,
                descricao=description, budgeted_value=value, notes=notes,
            )
        except (BudgetDomainError, RuntimeError) as error:
            self.view.set_status(str(error), error=True)
            return
        self.view.set_status("Orçamento cadastrado com sucesso.")
        self.refresh()

    def open_edit_dialog(self) -> None:
        budget_id = self.view.selected_budget_id()
        if budget_id is None:
            self.view.set_status("Selecione uma linha com orçamento para editar.", error=True)
            return
        budget = self.service.get_budget(budget_id)
        if budget is None:
            self.view.set_status("Orçamento não encontrado.", error=True)
            return
        try:
            options = self.catalog_service.list_budget_options() if self.catalog_service else ()
        except RuntimeError as error:
            self.view.set_status(f"Falha ao carregar Catálogo: {error}", error=True)
            return
        dialog = BudgetDialog(self.view, budget, catalog_options=options)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        description, value, notes = dialog.update_values()
        try:
            self.service.update_budget(
                budget.id, descricao=description, budgeted_value=value, notes=notes
            )
        except (BudgetDomainError, RuntimeError) as error:
            self.view.set_status(str(error), error=True)
            return
        self.view.set_status("Orçamento atualizado com sucesso.")
        self.refresh()
