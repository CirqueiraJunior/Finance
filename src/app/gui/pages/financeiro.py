from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.cashflow_entry import CashflowCategory, CashflowEntry


class IndirectRevenueDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nova Receita Indireta")
        self.setMinimumWidth(420)
        layout = QFormLayout(self)
        self.entry_date = QDateEdit(QDate.currentDate())
        self.entry_date.setCalendarPopup(True)
        self.description = QLineEdit()
        self.value = QLineEdit()
        self.value.setPlaceholderText("0,0000")
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(90)
        layout.addRow("Data", self.entry_date)
        layout.addRow("Descrição", self.description)
        layout.addRow("Valor", self.value)
        layout.addRow("Observação", self.notes)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def values(self) -> tuple[date, str, str, str]:
        selected = self.entry_date.date()
        return (
            date(selected.year(), selected.month(), selected.day()),
            self.description.text(),
            self.value.text().replace(".", "").replace(",", "."),
            self.notes.toPlainText(),
        )


class FinanceiroPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)
        title = QLabel("Fluxo de Caixa")
        title.setObjectName("pageTitle")
        description = QLabel("Receitas Diretas do BOE e Receitas Indiretas manuais.")
        description.setObjectName("pageDescription")

        filter_layout = QHBoxLayout()
        self.year_filter = QSpinBox()
        self.year_filter.setRange(2000, 9999)
        self.year_filter.setValue(date.today().year)
        self.month_filter = QSpinBox()
        self.month_filter.setRange(1, 12)
        self.month_filter.setValue(date.today().month)
        self.filter_button = QPushButton("Aplicar filtro")
        self.new_indirect_button = QPushButton("Nova Receita Indireta")
        self.new_indirect_button.setObjectName("primaryButton")
        filter_layout.addWidget(QLabel("Ano"))
        filter_layout.addWidget(self.year_filter)
        filter_layout.addWidget(QLabel("Mês"))
        filter_layout.addWidget(self.month_filter)
        filter_layout.addWidget(self.filter_button)
        filter_layout.addStretch()
        filter_layout.addWidget(self.new_indirect_button)

        summary_layout = QHBoxLayout()
        self.direct_total = self._summary_card("Receita Direta", summary_layout)
        self.indirect_total = self._summary_card("Receita Indireta", summary_layout)
        self.revenue_total = self._summary_card("Receita Total", summary_layout)
        self.entries_table = QTableWidget(0, 5)
        self.entries_table.setHorizontalHeaderLabels(
            ["Data", "Descrição", "Categoria", "Origem", "Valor"]
        )
        self.entries_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.entries_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.entries_table.horizontalHeader().setStretchLastSection(True)
        self.operation_status = QLabel("Fluxo de Caixa pronto.")
        self.operation_status.setObjectName("operationStatus")
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(filter_layout)
        layout.addLayout(summary_layout)
        layout.addWidget(self.entries_table, 1)
        layout.addWidget(self.operation_status)

    @staticmethod
    def _summary_card(title: str, layout: QHBoxLayout) -> QLabel:
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

    def show_entries(self, entries: list[CashflowEntry]) -> None:
        self.entries_table.setRowCount(len(entries))
        direct = Decimal("0")
        indirect = Decimal("0")
        for row, entry in enumerate(entries):
            if entry.categoria == CashflowCategory.DIRECT_REVENUE.value:
                direct += entry.valor
            else:
                indirect += entry.valor
            values = [
                entry.data_lancamento.strftime("%d/%m/%Y"), entry.descricao,
                self._category_label(entry.categoria), entry.origem,
                self.format_currency(entry.valor),
            ]
            for column, value in enumerate(values):
                self.entries_table.setItem(row, column, QTableWidgetItem(value))
        self.direct_total.setText(self.format_currency(direct))
        self.indirect_total.setText(self.format_currency(indirect))
        self.revenue_total.setText(self.format_currency(direct + indirect))
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
        return "Receita Direta" if category == "RECEITA_DIRETA" else "Receita Indireta"
