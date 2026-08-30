from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QTabWidget,
)

from app.models.entity import Entity
from app.models.target_entry import TargetEntry, TargetIndicator
from app.services.target_service import TargetVsActual
from app.services.ranking_service import AnnualRankingEntry, RankingEntry
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
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        self.tabs = QTabWidget()
        operational = QWidget()
        layout = QVBoxLayout(operational)
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

        self.table = QTableWidget(0, 8)
        self.table.setObjectName("targetsTable")
        self.table.setHorizontalHeaderLabels(
            ["Código", "Entidade", "Indicador", "Meta", "Realizado",
             "Diferença", "Atingimento %", "Observação"]
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
        self.tabs.addTab(operational, "Meta x Realizado")
        self.ranking_tab = QWidget()
        ranking_layout = QVBoxLayout(self.ranking_tab)
        ranking_filters = QHBoxLayout()
        self.ranking_year = QSpinBox()
        self.ranking_year.setRange(2000, 9999)
        self.ranking_year.setValue(date.today().year)
        self.ranking_quarter = QComboBox()
        for quarter in range(1, 5):
            self.ranking_quarter.addItem(f"{quarter}º Trimestre", quarter)
        self.ranking_refresh = QPushButton("Atualizar ranking")
        self.ranking_entity = QComboBox()
        self.ranking_entity.addItem("Todas as Entidades", None)
        ranking_filters.addWidget(QLabel("Ano"))
        ranking_filters.addWidget(self.ranking_year)
        ranking_filters.addWidget(QLabel("Trimestre"))
        ranking_filters.addWidget(self.ranking_quarter)
        ranking_filters.addWidget(QLabel("Entidade"))
        ranking_filters.addWidget(self.ranking_entity, 1)
        ranking_filters.addWidget(self.ranking_refresh)
        self.champions_title = QLabel("CAMPEÕES DO TRIMESTRE")
        self.champions_title.setObjectName("sectionTitle")
        self.champions = QLabel("Apuração ainda não carregada.")
        self.ranking_title = QLabel("CLASSIFICAÇÃO GERAL DO TRIMESTRE")
        self.ranking_title.setObjectName("sectionTitle")
        headers = ["Posição", "Código", "Entidade", "Meta Total", "Realizado Total",
                   "% Atingimento", "Captações", "Cancelamentos", "Pts Faturamento",
                   "Pts Captação", "Pts Cancelamento", "Score Final", "Situação", "Premiação"]
        self.ranking_table = QTableWidget(0, len(headers))
        self.ranking_table.setHorizontalHeaderLabels(headers)
        self.ranking_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ranking_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.entity_detail = QLabel("Selecione uma Entidade para consultar sua visão detalhada.")
        self.entity_detail.setObjectName("operationStatus")
        self.annual_title = QLabel("VISÃO ANUAL INFORMATIVA — sem soma de scores")
        self.annual_title.setObjectName("sectionTitle")
        self.annual_table = QTableWidget(0, 9)
        self.annual_table.setHorizontalHeaderLabels(
            ["Código", "Entidade", "T1", "T2", "T3", "T4", "Classificações", "Prêmios", "Total Recebido"]
        )
        self.annual_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        ranking_layout.addLayout(ranking_filters)
        ranking_layout.addWidget(self.champions_title)
        ranking_layout.addWidget(self.champions)
        ranking_layout.addWidget(self.ranking_title)
        ranking_layout.addWidget(self.ranking_table, 2)
        ranking_layout.addWidget(self.entity_detail)
        ranking_layout.addWidget(self.annual_title)
        ranking_layout.addWidget(self.annual_table, 1)
        self.tabs.addTab(self.ranking_tab, "Ranking e Premiação")
        outer.addWidget(self.tabs)

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
                  comparison.notes or "—",
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

    def show_ranking(self, rows: list[RankingEntry], annual: list[AnnualRankingEntry]) -> None:
        selected = self.ranking_entity.currentData()
        self.ranking_entity.blockSignals(True)
        self.ranking_entity.clear()
        self.ranking_entity.addItem("Todas as Entidades", None)
        for row in rows:
            self.ranking_entity.addItem(f"{row.entity_code} — {row.entity_name}", row.entity_id)
        self.ranking_entity.setCurrentIndex(max(0, self.ranking_entity.findData(selected)))
        self.ranking_entity.blockSignals(False)
        visible = [row for row in rows if selected is None or row.entity_id == selected]
        self.ranking_table.setRowCount(len(visible))
        for row_index, row in enumerate(visible):
            situation = "Classificada" if row.classified else "Desclassificada"
            if row.technical_tie:
                situation += " — empate técnico"
            values = [row.position or "-", row.entity_code, row.entity_name,
                      self.number(row.target_total), self.number(row.actual_total),
                      self.percentage(row.achievement), self.number(row.captures),
                      self.number(row.cancellations), row.billing_points,
                      row.capture_points, row.cancellation_points, row.score,
                      situation, self.currency(row.award) if row.award is not None else "-"]
            for column, value in enumerate(values):
                self.ranking_table.setItem(row_index, column, QTableWidgetItem(str(value)))
        winners = [row for row in rows if row.award is not None]
        self.champions.setText("\n".join(
            f"{row.position}º lugar — {row.entity_name} — {self.currency(row.award)}"
            for row in winners
        ) or "Nenhum campeão definido para o período.")
        self.annual_table.setRowCount(len(annual))
        for index, row in enumerate(annual):
            values = [row.entity_code, row.entity_name,
                      *(position or "-" for position in row.positions),
                      row.classified_quarters, row.award_count, self.currency(row.award_total)]
            for column, value in enumerate(values):
                self.annual_table.setItem(index, column, QTableWidgetItem(str(value)))
        detail = next((row for row in rows if row.entity_id == selected), None)
        self.entity_detail.setText(
            "Selecione uma Entidade para consultar sua visão detalhada." if detail is None else
            f"Consultas: Meta {self.number(detail.meta_queries)} | Realizado {self.number(detail.actual_queries)}  •  "
            f"Registros: Meta {self.number(detail.meta_registrations)} | Realizado {self.number(detail.actual_registrations)}  •  "
            f"Total: {self.number(detail.target_total)} / {self.number(detail.actual_total)}  •  "
            f"Atingimento: {self.percentage(detail.achievement)}  •  Captações: {self.number(detail.captures)}  •  "
            f"Cancelamentos: {self.number(detail.cancellations)}  •  Pontos: {detail.billing_points}+{detail.capture_points}+{detail.cancellation_points}={detail.score}  •  "
            f"Posição: {detail.position or '-'}  •  Premiação: {self.currency(detail.award) if detail.award else '-'}"
        )
        self.ranking_table.resizeColumnsToContents()

    @staticmethod
    def currency(value: Decimal) -> str:
        formatted = f"{value:,.2f}"
        return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @staticmethod
    def number(value: Decimal) -> str:
        formatted = f"{value:,.4f}"
        return formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @staticmethod
    def percentage(value: Decimal | None) -> str:
        return "—" if value is None else f"{value:.4f}%".replace(".", ",")
