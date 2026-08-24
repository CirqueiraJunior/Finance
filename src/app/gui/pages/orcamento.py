from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.budget_entry import BudgetEntry
from app.models.cashflow_entry import EXPENSE_CATEGORIES, CashflowCategory, CashflowType
from app.services.budget_service import BudgetVsActual, REVENUE_CATEGORIES


class BudgetDialog(QDialog):
    def __init__(
        self, parent: QWidget | None = None, budget: BudgetEntry | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar Orçamento" if budget else "Novo Orçamento")
        self.setMinimumWidth(430)
        layout = QFormLayout(self)
        self.year = QSpinBox()
        self.year.setRange(2000, 9999)
        self.year.setValue(budget.periodo_ano if budget else date.today().year)
        self.month = QSpinBox()
        self.month.setRange(1, 12)
        self.month.setValue(budget.periodo_mes if budget else date.today().month)
        self.entry_type = QComboBox()
        self.entry_type.addItem("Receita", CashflowType.REVENUE.value)
        self.entry_type.addItem("Despesa", CashflowType.EXPENSE.value)
        self.category = QComboBox()
        self.budgeted_value = QLineEdit()
        self.budgeted_value.setPlaceholderText("0,0000")
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(90)
        layout.addRow("Ano", self.year)
        layout.addRow("Mês", self.month)
        layout.addRow("Tipo", self.entry_type)
        layout.addRow("Categoria", self.category)
        layout.addRow("Valor Orçado", self.budgeted_value)
        layout.addRow("Observação", self.notes)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.entry_type.currentIndexChanged.connect(self.update_categories)
        if budget:
            self.entry_type.setCurrentIndex(
                0 if budget.tipo == CashflowType.REVENUE.value else 1
            )
        self.update_categories()
        if budget:
            category_index = self.category.findData(budget.categoria)
            self.category.setCurrentIndex(category_index)
            self.budgeted_value.setText(self.format_decimal(budget.valor_orcado))
            self.notes.setPlainText(budget.observacao or "")
            for widget in (self.year, self.month, self.entry_type, self.category):
                widget.setEnabled(False)

    def update_categories(self) -> None:
        selected = self.category.currentData()
        self.category.clear()
        categories = (
            REVENUE_CATEGORIES
            if self.entry_type.currentData() == CashflowType.REVENUE.value
            else EXPENSE_CATEGORIES
        )
        for category in categories:
            self.category.addItem(self.category_label(category.value), category.value)
        index = self.category.findData(selected)
        if index >= 0:
            self.category.setCurrentIndex(index)

    def create_values(self) -> tuple[int, int, str, str, str, str]:
        return (
            self.year.value(), self.month.value(), self.entry_type.currentData(),
            self.category.currentData(), self.normalized_value(),
            self.notes.toPlainText(),
        )

    def update_values(self) -> tuple[str, str]:
        return self.normalized_value(), self.notes.toPlainText()

    def normalized_value(self) -> str:
        return self.budgeted_value.text().replace(".", "").replace(",", ".")

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
        self.month_filter = QComboBox()
        self.month_filter.addItem("Ano completo", 0)
        for month in range(1, 13):
            self.month_filter.addItem(f"{month:02d}", month)
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

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            ["Tipo", "Categoria", "Orçado", "Realizado", "Desvio", "Desvio %"]
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
        value = QLabel("R$ 0,0000")
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
        self.month_filter.setCurrentIndex(0 if month is None else month)

    def show_result(
        self, result: BudgetVsActual, budgets: list[BudgetEntry]
    ) -> None:
        budget_ids = {
            (budget.tipo, budget.categoria): budget.id for budget in budgets
        }
        self.table.setRowCount(len(result.comparisons))
        for row, comparison in enumerate(result.comparisons):
            values = [
                comparison.entry_type,
                BudgetDialog.category_label(comparison.category),
                self.currency(comparison.budgeted),
                self.currency(comparison.actual),
                self.currency(comparison.absolute_variance),
                "—" if comparison.percentage_variance is None
                else f"{comparison.percentage_variance:.4f}%".replace(".", ","),
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
        formatted = f"{value:,.4f}"
        return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")
