from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.budget_entry import BudgetEntry
from app.models.cashflow_entry import EXPENSE_CATEGORIES, CashflowCategory, CashflowType
from app.services.budget_service import BudgetVsActual, REVENUE_CATEGORIES
from app.services.cashflow_catalog_service import CashflowCatalogOption
from app.widgets import BRLCurrencyEdit, MonthComboBox


class BudgetDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, budget: BudgetEntry | None = None,
        *, catalog_options: tuple[CashflowCatalogOption, ...] = (),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar Orçamento" if budget else "Novo Orçamento")
        self.setMinimumWidth(430)
        layout = QFormLayout(self)
        self.year = QSpinBox()
        self.year.setRange(2000, 9999)
        self.year.setValue(budget.periodo_ano if budget else date.today().year)
        self.month = MonthComboBox()
        self.month.set_month(budget.periodo_mes if budget else date.today().month)
        self.entry_type = QComboBox()
        self.entry_type.addItem("Receita", CashflowType.REVENUE.value)
        self.entry_type.addItem("Despesa", CashflowType.EXPENSE.value)
        self.entry_type.setEnabled(False)
        self.category = QComboBox()
        self.description = QComboBox()
        options = [
            option for option in catalog_options
            if option.movement_type in {
                CashflowType.REVENUE.value, CashflowType.EXPENSE.value
            }
            and (budget is None or (
                option.category == budget.categoria
                and option.movement_type == budget.tipo
            ))
        ]
        if budget and budget.descricao and not any(
            option.description == budget.descricao
            and option.category == budget.categoria
            and option.movement_type == budget.tipo
            for option in options
        ):
            options.append(CashflowCatalogOption(
                budget.descricao, budget.categoria, budget.tipo
            ))
        self._catalog_options = tuple(options)
        self.description.addItem("Selecione a descrição...", None)
        for value in dict.fromkeys(option.description for option in self._catalog_options):
            self.description.addItem(value, value)
        self.budgeted_value = BRLCurrencyEdit()
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(90)
        layout.addRow("Ano", self.year)
        layout.addRow("Mês", self.month)
        layout.addRow("Descrição", self.description)
        layout.addRow("Categoria", self.category)
        layout.addRow("Tipo", self.entry_type)
        layout.addRow("Valor Orçado", self.budgeted_value)
        layout.addRow("Observação", self.notes)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.description.currentIndexChanged.connect(self.update_categories)
        self.category.currentIndexChanged.connect(self.update_type)
        self.update_categories()
        if budget:
            description_index = self.description.findData(budget.descricao)
            self.description.setCurrentIndex(description_index)
            category_index = self.category.findData(budget.categoria)
            self.category.setCurrentIndex(category_index)
            self.update_type()
            self.budgeted_value.set_decimal_value(budget.valor_orcado)
            self.notes.setPlainText(budget.observacao or "")
            for widget in (self.year, self.month, self.entry_type, self.category):
                widget.setEnabled(False)

    def update_categories(self) -> None:
        description = self.description.currentData()
        self.category.clear()
        matches = [option for option in self._catalog_options
                   if option.description == description]
        if not matches:
            self.category.addItem("Selecione a categoria...", None)
        elif len(matches) > 1:
            self.category.addItem("Selecione a categoria...", None)
        for option in matches:
            self.category.addItem(self.category_label(option.category), option.category)
        self.update_type()

    def update_type(self) -> None:
        description = self.description.currentData()
        category = self.category.currentData()
        option = next((item for item in self._catalog_options
                       if item.description == description and item.category == category), None)
        index = self.entry_type.findData(option.movement_type if option else None)
        self.entry_type.setCurrentIndex(index)

    def _accept_if_valid(self) -> None:
        if self.description.currentData() is None:
            QMessageBox.warning(self, "Descrição obrigatória", "Selecione a Descrição.")
            return
        if self.category.currentData() is None or self.entry_type.currentData() is None:
            QMessageBox.warning(self, "Catálogo inválido", "Selecione uma combinação válida de Descrição e Categoria.")
            return
        self.accept()

    def create_values(self) -> tuple[int, int, str, str, str, str, str]:
        return (
            self.year.value(), self.month.month(), self.entry_type.currentData(),
            self.category.currentData(), self.description.currentData(), self.normalized_value(),
            self.notes.toPlainText(),
        )

    def update_values(self) -> tuple[str, str, str]:
        return self.description.currentData(), self.normalized_value(), self.notes.toPlainText()

    def normalized_value(self) -> str:
        return str(self.budgeted_value.decimal_value())

    @staticmethod
    def category_label(value: str) -> str:
        return value.replace("_", " ").title()

    @staticmethod
    def format_decimal(value: Decimal) -> str:
        return f"{value:.4f}".replace(".", ",")


class OrcamentoPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)
        title = QLabel("Orçado x Realizado")
        title.setObjectName("pageTitle")
        description = QLabel("Orçamento mensal ou anual comparado ao Fluxo de Caixa.")
        description.setObjectName("pageDescription")

        filters = QHBoxLayout()
        self.year_filter = QSpinBox()
        self.year_filter.setRange(2000, 9999)
        self.year_filter.setValue(date.today().year)
        self.month_filter = MonthComboBox(include_all=True)
        self.filter_button = QPushButton("Aplicar filtro")
        self.new_button = QPushButton("Novo Orçamento")
        self.new_button.setObjectName("primaryButton")
        self.edit_button = QPushButton("Editar Orçamento")
        filters.addWidget(QLabel("Ano"))
        filters.addWidget(self.year_filter)
        filters.addWidget(QLabel("Mês"))
        filters.addWidget(self.month_filter)
        filters.addWidget(self.filter_button)
        filters.addStretch()
        filters.addWidget(self.edit_button)
        filters.addWidget(self.new_button)

        cards = QHBoxLayout()
        self.budgeted_revenue = self._card("Receita Orçada", cards)
        self.actual_revenue = self._card("Receita Realizada", cards)
        self.budgeted_expense = self._card("Despesa Orçada", cards)
        self.actual_expense = self._card("Despesa Realizada", cards)
        self.actual_result = self._card("Resultado Realizado", cards)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Tipo", "Descrição", "Categoria", "Orçado", "Realizado", "Desvio", "Desvio %", "Observação"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.status = QLabel("Orçamento pronto.")
        self.status.setObjectName("operationStatus")
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(filters)
        layout.addLayout(cards)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.status)

    @staticmethod
    def _card(title: str, layout: QHBoxLayout) -> QLabel:
        card = QWidget()
        card.setObjectName("summaryCard")
        card_layout = QVBoxLayout(card)
        label = QLabel(title)
        label.setObjectName("summaryLabel")
        value = QLabel("R$ 0,00")
        value.setObjectName("summaryValue")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        layout.addWidget(card, 1)
        return value

    def selected_period(self) -> tuple[int, int | None]:
        month = self.month_filter.currentData()
        return self.year_filter.value(), month or None

    def set_period(self, year: int, month: int | None) -> None:
        self.year_filter.setValue(year)
        self.month_filter.set_month(month)

    def show_result(
        self, result: BudgetVsActual, budgets: list[BudgetEntry]
    ) -> None:
        budget_ids = {
            (budget.tipo, budget.categoria): budget.id for budget in budgets
        }
        budget_notes = {
            (budget.tipo, budget.categoria): (budget.observacao or "—")
            for budget in budgets
        }
        self.table.setRowCount(len(result.comparisons))
        for row, comparison in enumerate(result.comparisons):
            values = [
                comparison.entry_type,
                comparison.description or "—",
                BudgetDialog.category_label(comparison.category),
                self.currency(comparison.budgeted),
                self.currency(comparison.actual),
                self.currency(comparison.absolute_variance),
                "—" if comparison.percentage_variance is None
                else f"{comparison.percentage_variance:.4f}%".replace(".", ","),
                budget_notes.get((comparison.entry_type, comparison.category), "—"),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(
                        Qt.ItemDataRole.UserRole,
                        budget_ids.get((comparison.entry_type, comparison.category)),
                    )
                self.table.setItem(row, column, item)
        summary = result.summary
        self.budgeted_revenue.setText(self.currency(summary.budgeted_revenue))
        self.actual_revenue.setText(self.currency(summary.actual_revenue))
        self.budgeted_expense.setText(self.currency(summary.budgeted_expense))
        self.actual_expense.setText(self.currency(summary.actual_expense))
        self.actual_result.setText(self.currency(summary.actual_result))
        self.table.resizeColumnsToContents()

    def selected_budget_id(self) -> int | None:
        row = self.table.currentRow()
        if row < 0 or self.table.item(row, 0) is None:
            return None
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status.setText(message)
        self.status.setProperty("error", error)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    @staticmethod
    def currency(value: Decimal) -> str:
        formatted = f"{value:,.2f}"
        return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")
