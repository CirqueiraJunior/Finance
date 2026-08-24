from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.cashflow_entry import EXPENSE_CATEGORIES, CashflowCategory, CashflowType
from app.models.investment_movement import InvestmentMovementType
from app.services.financial_flow_service import FinancialFlowSummary, FinancialMovement


class CashflowEntryDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Novo Lançamento")
        self.setMinimumWidth(430)
        layout = QFormLayout(self)
        self.entry_type = QComboBox()
        self.entry_type.addItem("Receita", CashflowType.REVENUE.value)
        self.entry_type.addItem("Despesa", CashflowType.EXPENSE.value)
        self.entry_type.addItem("Aplicação", InvestmentMovementType.APPLICATION.value)
        self.entry_type.addItem("Resgate", InvestmentMovementType.REDEMPTION.value)
        self.entry_date = QDateEdit(QDate.currentDate())
        self.entry_date.setCalendarPopup(True)
        self.entry_date.setDisplayFormat("dd/MM/yyyy")
        self.description = QLineEdit()
        self.category = QComboBox()
        self.value = QLineEdit()
        self.value.setPlaceholderText("0,0000")
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(90)
        self.available_balance = QLabel("Saldo aplicado disponível: R$ 0,0000")
        layout.addRow("Tipo", self.entry_type)
        layout.addRow("Data", self.entry_date)
        layout.addRow("Descrição", self.description)
        self.category_label = QLabel("Categoria")
        layout.addRow(self.category_label, self.category)
        layout.addRow("Valor", self.value)
        layout.addRow("Observação", self.notes)
        layout.addRow(self.available_balance)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        self.entry_type.currentIndexChanged.connect(self.update_fields)
        self.update_fields()

    def update_fields(self) -> None:
        entry_type = self.entry_type.currentData()
        uses_category = entry_type in {CashflowType.REVENUE.value, CashflowType.EXPENSE.value}
        self.category.setVisible(uses_category)
        self.category_label.setVisible(uses_category)
        self.available_balance.setVisible(entry_type == InvestmentMovementType.REDEMPTION.value)
        self.category.clear()
        if entry_type == CashflowType.REVENUE.value:
            self.category.addItem("Receita Indireta", CashflowCategory.INDIRECT_REVENUE.value)
        elif entry_type == CashflowType.EXPENSE.value:
            for category in EXPENSE_CATEGORIES:
                self.category.addItem(self.category_text(category.value), category.value)

    def set_available_balance(self, value: Decimal) -> None:
        self.available_balance.setText(
            f"Saldo aplicado disponível: {FinanceiroPage.format_currency(value)}"
        )

    def values(self) -> tuple[str, date, str, str | None, str, str]:
        return (
            self.entry_type.currentData(), self.entry_date.date().toPython(),
            self.description.text(), self.category.currentData(),
            self.value.text().replace(".", "").replace(",", "."),
            self.notes.toPlainText(),
        )

    @staticmethod
    def category_text(category: str) -> str:
        return category.replace("_", " ").title()


class IndirectRevenueDialog(CashflowEntryDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nova Receita Indireta")
        self.entry_type.setEnabled(False)


class FinanceiroPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)
        title = QLabel("Fluxo de Caixa")
        title.setObjectName("pageTitle")
        description = QLabel("Receitas, despesas, aplicações e resgates no mesmo fluxo financeiro.")
        description.setObjectName("pageDescription")
        filters = QHBoxLayout()
        self.year_filter = QSpinBox()
        self.year_filter.setRange(2000, 9999)
        self.year_filter.setValue(date.today().year)
        self.month_filter = QSpinBox()
        self.month_filter.setRange(1, 12)
        self.month_filter.setValue(date.today().month)
        self.filter_button = QPushButton("Aplicar filtro")
        self.new_entry_button = QPushButton("Novo Lançamento")
        self.new_entry_button.setObjectName("primaryButton")
        self.new_indirect_button = self.new_entry_button
        for label, widget in (("Ano", self.year_filter), ("Mês", self.month_filter)):
            filters.addWidget(QLabel(label))
            filters.addWidget(widget)
        filters.addWidget(self.filter_button)
        filters.addStretch()
        filters.addWidget(self.new_entry_button)

        cards = QGridLayout()
        self.revenue_total = self._card("Receita Total", cards, 0, 0)
        self.expense_total = self._card("Despesa Total", cards, 0, 1)
        self.applications_total = self._card("Aplicações", cards, 0, 2)
        self.redemptions_total = self._card("Resgates", cards, 0, 3)
        self.operational_result = self._card("Resultado Operacional", cards, 1, 0)
        self.cash_movement = self._card("Movimentação de Caixa", cards, 1, 1)
        self.applied_balance = self._card("Saldo Aplicado", cards, 1, 2)
        self.direct_total = QLabel()
        self.indirect_total = QLabel()
        self.monthly_balance = self.operational_result

        self.entries_table = QTableWidget(0, 6)
        self.entries_table.setHorizontalHeaderLabels(
            ["Data", "Tipo", "Descrição", "Categoria", "Origem", "Valor"]
        )
        self.entries_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.entries_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.entries_table.horizontalHeader().setStretchLastSection(True)
        self.operation_status = QLabel("Fluxo de Caixa pronto.")
        self.operation_status.setObjectName("operationStatus")
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(filters)
        layout.addLayout(cards)
        layout.addWidget(self.entries_table, 1)
        layout.addWidget(self.operation_status)

    @staticmethod
    def _card(title: str, layout: QGridLayout, row: int, column: int) -> QLabel:
        card = QWidget()
        card.setObjectName("summaryCard")
        card_layout = QVBoxLayout(card)
        label = QLabel(title)
        label.setObjectName("summaryLabel")
        value = QLabel("R$ 0,0000")
        value.setObjectName("summaryValue")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        layout.addWidget(card, row, column)
        return value

    def show_financial_flow(self, movements: list[FinancialMovement], summary: FinancialFlowSummary) -> None:
        self.entries_table.setRowCount(len(movements))
        for row, movement in enumerate(movements):
            values = (
                movement.movement_date.strftime("%d/%m/%Y"), movement.movement_type,
                movement.description,
                self._category_label(movement.category) if movement.category else "—",
                movement.origin or "—", self.format_currency(movement.value),
            )
            for column, value in enumerate(values):
                self.entries_table.setItem(row, column, QTableWidgetItem(value))
        self.direct_total.setText(self.format_currency(summary.direct_revenue))
        self.indirect_total.setText(self.format_currency(summary.indirect_revenue))
        self.revenue_total.setText(self.format_currency(summary.total_revenue))
        self.expense_total.setText(self.format_currency(summary.total_expense))
        self.applications_total.setText(self.format_currency(summary.applications))
        self.redemptions_total.setText(self.format_currency(summary.redemptions))
        self.operational_result.setText(self.format_currency(summary.operational_result))
        self.cash_movement.setText(self.format_currency(summary.cash_movement))
        self.applied_balance.setText(self.format_currency(summary.applied_balance))
        self.entries_table.resizeColumnsToContents()

    def selected_period(self) -> tuple[int, int]:
        return self.year_filter.value(), self.month_filter.value()

    def set_period(self, year: int, month: int) -> None:
        self.year_filter.setValue(year)
        self.month_filter.setValue(month)

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.operation_status.setText(message)
        self.operation_status.setProperty("error", error)
        self.operation_status.style().unpolish(self.operation_status)
        self.operation_status.style().polish(self.operation_status)

    @staticmethod
    def format_currency(value: Decimal) -> str:
        formatted = f"{value:,.4f}"
        return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @staticmethod
    def _category_label(category: str) -> str:
        return category.replace("_", " ").title()
