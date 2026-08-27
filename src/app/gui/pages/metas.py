from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.models.entity import Entity
from app.models.target_entry import TargetEntry, TargetIndicator
from app.services.target_service import TargetVsActual
from app.widgets import BrazilianDecimalEdit, MonthComboBox


class TargetDialog(QDialog):
    def __init__(
        self, entities: list[Entity], parent: QWidget | None = None,
        target: TargetEntry | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar Meta" if target else "Nova Meta")
        self.setMinimumWidth(440)
        layout = QFormLayout(self)
        self.year = QSpinBox()
        self.year.setRange(2000, 9999)
        self.year.setValue(target.periodo_ano if target else date.today().year)
        self.month = MonthComboBox()
        self.month.set_month(target.periodo_mes if target else date.today().month)
        self.entity = QComboBox()
        for entity in entities:
            name = entity.nome_oficial or entity.nome
            self.entity.addItem(f"{entity.codigo_entidade} — {name}", entity.id)
        self.indicator = QComboBox()
        self.indicator.addItem("Consultas", TargetIndicator.QUERIES.value)
        self.indicator.addItem("Registros", TargetIndicator.REGISTRATIONS.value)
        self.target_value = BrazilianDecimalEdit()
        self.actual_value = BrazilianDecimalEdit()
        self.notes = QPlainTextEdit()
        self.notes.setMaximumHeight(90)
        layout.addRow("Ano", self.year)
        layout.addRow("Mês", self.month)
        layout.addRow("Entidade", self.entity)
        layout.addRow("Indicador", self.indicator)
        layout.addRow("Valor da Meta", self.target_value)
        layout.addRow("Realizado disponível", self.actual_value)
        layout.addRow("Observação", self.notes)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)
        if target:
            self.entity.setCurrentIndex(self.entity.findData(target.entity_id))
            self.indicator.setCurrentIndex(self.indicator.findData(target.indicador))
            self.target_value.set_decimal_value(target.valor_meta)
            self.actual_value.set_decimal_value(target.valor_realizado)
            self.notes.setPlainText(target.observacao or "")
            for widget in (
                self.year, self.month, self.entity, self.indicator, self.actual_value,
            ):
                widget.setEnabled(False)

    def create_values(self) -> tuple[int, int, int, str, str, str, str]:
        return (
            self.year.value(), self.month.month(), self.entity.currentData(),
            self.indicator.currentData(), str(self.target_value.decimal_value()),
            str(self.actual_value.decimal_value()), self.notes.toPlainText(),
        )

    def update_values(self) -> tuple[str, str]:
        return str(self.target_value.decimal_value()), self.notes.toPlainText()

    @staticmethod
    def normalized(value: str) -> str:
        return value.replace(".", "").replace(",", ".")

    @staticmethod
    def format_decimal(value: Decimal) -> str:
        return f"{value:.4f}".replace(".", ",")


class MetasPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)
        title = QLabel("Meta x Realizado")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Indicadores operacionais de Consultas e Registros por Entidade."
        )
        description.setObjectName("pageDescription")

        filters = QHBoxLayout()
        self.year_filter = QSpinBox()
        self.year_filter.setRange(2000, 9999)
        self.year_filter.setValue(date.today().year)
        self.month_filter = MonthComboBox()
        self.month_filter.set_month(date.today().month)
        self.indicator_filter = QComboBox()
        self.indicator_filter.addItem("Consultas", TargetIndicator.QUERIES.value)
        self.indicator_filter.addItem("Registros", TargetIndicator.REGISTRATIONS.value)
        self.entity_filter = QComboBox()
        self.entity_filter.addItem("Todas as Entidades", None)
        self.filter_button = QPushButton("Aplicar filtro")
        self.new_button = QPushButton("Nova Meta")
        self.new_button.setObjectName("primaryButton")
        self.edit_button = QPushButton("Editar Meta")
        filters.addWidget(QLabel("Ano"))
        filters.addWidget(self.year_filter)
        filters.addWidget(QLabel("Mês"))
        filters.addWidget(self.month_filter)
        filters.addWidget(QLabel("Indicador"))
        filters.addWidget(self.indicator_filter)
        filters.addWidget(QLabel("Entidade"))
        filters.addWidget(self.entity_filter, 1)
        filters.addWidget(self.filter_button)
        filters.addWidget(self.edit_button)
        filters.addWidget(self.new_button)

        cards = QHBoxLayout()
        self.entity_count = self._card("Entidades", cards, "0")
        self.target_total = self._card("Meta", cards)
        self.actual_total = self._card("Realizado", cards)
        self.difference_total = self._card("Diferença", cards)
        self.achievement_total = self._card("Atingimento", cards, "—")

        self.table = QTableWidget(0, 7)
        self.table.setObjectName("targetsTable")
        self.table.setHorizontalHeaderLabels(
            ["Código", "Entidade", "Indicador", "Meta", "Realizado",
             "Diferença", "Atingimento %"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.empty_state = QLabel("Nenhuma Meta cadastrada para os filtros selecionados.")
        self.empty_state.setObjectName("pageDescription")
        self.status = QLabel("Meta x Realizado pronto.")
        self.status.setObjectName("operationStatus")
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(filters)
        layout.addLayout(cards)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.status)

    @staticmethod
    def _card(title: str, layout: QHBoxLayout, initial: str = "0,0000") -> QLabel:
        card = QWidget()
        card.setObjectName("summaryCard")
        card_layout = QVBoxLayout(card)
        label = QLabel(title)
        label.setObjectName("summaryLabel")
        value = QLabel(initial)
        value.setObjectName("summaryValue")
        card_layout.addWidget(label)
        card_layout.addWidget(value)
        layout.addWidget(card, 1)
        return value

    def set_entities(self, entities: list[Entity]) -> None:
        selected = self.entity_filter.currentData()
        self.entity_filter.clear()
        self.entity_filter.addItem("Todas as Entidades", None)
        for entity in entities:
            name = entity.nome_oficial or entity.nome
            self.entity_filter.addItem(f"{entity.codigo_entidade} — {name}", entity.id)
        index = self.entity_filter.findData(selected)
        self.entity_filter.setCurrentIndex(max(index, 0))

    def selected_filters(self) -> tuple[int, int, str, int | None]:
        return (
            self.year_filter.value(), self.month_filter.currentData(),
            self.indicator_filter.currentData(), self.entity_filter.currentData(),
        )

    def show_result(self, result: TargetVsActual) -> None:
        self.table.setRowCount(len(result.comparisons))
        for row, comparison in enumerate(result.comparisons):
            values = [
                str(comparison.entity_code), comparison.entity_name,
                comparison.indicator.title(), self.number(comparison.target),
                self.number(comparison.actual), self.number(comparison.difference),
                self.percentage(comparison.achievement_percentage),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, comparison.target_id)
                self.table.setItem(row, column, item)
        summary = result.summary
        self.entity_count.setText(str(summary.entity_count))
        self.target_total.setText(self.number(summary.target_total))
        self.actual_total.setText(self.number(summary.actual_total))
        self.difference_total.setText(self.number(summary.difference_total))
        self.achievement_total.setText(self.percentage(summary.achievement_percentage))
        self.empty_state.setVisible(not result.comparisons)
        self.table.resizeColumnsToContents()

    def selected_target_id(self) -> int | None:
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
    def number(value: Decimal) -> str:
        formatted = f"{value:,.4f}"
        return formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @staticmethod
    def percentage(value: Decimal | None) -> str:
        return "—" if value is None else f"{value:.4f}%".replace(".", ",")
