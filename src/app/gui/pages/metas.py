from PySide6.QtWidgets import QPlainTextEdit
from app.gui.import_workflow_steps import ImportWorkflowSteps
from app.gui.import_workflow_panel import ImportWorkflowPanel
from app.widgets.wheel_guard import WheelBlockedComboBox, WheelBlockedSpinBox, WheelBlockedTabWidget
from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPlainTextEdit, QProgressBar, QPushButton, QSpinBox, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QTabWidget,
)

from app.models.entity import Entity
from app.models.target_entry import TargetEntry, TargetIndicator
from app.gui.formatters import (
    format_currency, format_integer, format_number, format_percentage,
)
from app.services.target_service import TargetVsActual
from app.services.ranking_service import AnnualRankingEntry, RankingEntry
from app.widgets import BrazilianDecimalEdit, MonthComboBox
from app.widgets.entity_multi_select import EntityMultiSelectCombo
from app.widgets.year_combo import populate_year_combo


from PySide6.QtWidgets import QScrollArea

class TargetImportProgressDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Importação de Metas")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowCloseButtonHint, False)
        self.setMinimumWidth(380)
        layout = QVBoxLayout(self)
        title = QLabel("Processando importação...")
        title.setObjectName("sectionTitle")
        description = QLabel("Esta operação pode levar alguns instantes.")
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(self.progress)

    def reject(self) -> None:
        return


class TargetDialog(QDialog):
    def __init__(
        self, entities: list[Entity], parent: QWidget | None = None,
        target: TargetEntry | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar Meta" if target else "Nova Meta")
        self.setMinimumWidth(440)
        layout = QFormLayout(self)
        self.year = WheelBlockedSpinBox()
        self.year.setRange(2000, 9999)
        self.year.setValue(target.periodo_ano if target else date.today().year)
        self.month = MonthComboBox()
        self.month.set_month(target.periodo_mes if target else date.today().month)
        self.entity = WheelBlockedComboBox()
        for entity in entities:
            name = entity.nome_oficial or entity.nome
            self.entity.addItem(f"{entity.codigo_entidade} — {name}", entity.id)
        self.indicator = WheelBlockedComboBox()
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
        return format_number(value)


class MetasPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        self.tabs = WheelBlockedTabWidget()
        operational = QWidget()
        layout = QVBoxLayout(operational)
        layout.setContentsMargins(32, 2, 32, 12)
        layout.setSpacing(6)
        title = QLabel("Meta x Realizado")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Indicadores operacionais de Consultas e Registros por Entidade."
        )
        description.setObjectName("pageDescription")

        filter_panel = QWidget()
        filter_panel.setObjectName("dashboardFilterBar")
        filters = QHBoxLayout(filter_panel)
        self.year_filter = WheelBlockedComboBox()
        self.year_filter.setEnabled(False)
        self.month_filter = MonthComboBox()
        self.month_filter.set_month(date.today().month)
        self.indicator_filter = WheelBlockedComboBox()
        self.indicator_filter.addItem("Todas", "TODAS")
        self.indicator_filter.addItem("Consultas", TargetIndicator.QUERIES.value)
        self.indicator_filter.addItem("Registros", TargetIndicator.REGISTRATIONS.value)
        self.entity_filter = EntityMultiSelectCombo()
        self.filter_button = QPushButton("Aplicar filtro")
        self.filter_button.setEnabled(False)
        self.filter_button.setProperty("buttonRole", "toolbar")
        self.new_button = QPushButton("Nova Meta")
        self.new_button.setProperty("buttonRole", "primary")
        self.new_button.setObjectName("primaryButton")
        self.edit_button = QPushButton("Editar Meta")
        self.edit_button.setProperty("buttonRole", "secondary")
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

        import_area = QWidget()
        import_area.setObjectName("sectionCard")
        import_layout = QVBoxLayout(import_area)
        import_layout.setContentsMargins(10, 6, 10, 6)
        import_layout.setSpacing(4)
        self.import_summary = QLabel("Selecione um arquivo para validar a importação de Metas.")
        self.import_summary.setWordWrap(True)
        self.import_preview = QTableWidget(0, 6)
        self.import_preview.setHorizontalHeaderLabels(
            ["Linha", "Entidade", "Período", "Indicador", "Meta", "Realizado"]
        )
        self.import_preview.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.import_preview.setMinimumHeight(88)
        self.import_preview.setMaximumHeight(112)
        self.import_issues = QLabel()
        self.import_issues.setWordWrap(True)
        # Legacy action widgets remain internal until the controller/RBAC cleanup.
        # Shared visual workflow; existing module actions are unchanged.
        self.import_steps = ImportWorkflowSteps(steps=(
            "Selecionar", "Validar",
            "Comparar e autorizar", "Importar",
        ))

        validation_column = QVBoxLayout()
        validation_title = QLabel("Resultado da valida\u00e7\u00e3o")
        validation_title.setObjectName("sectionTitle")
        validation_column.addWidget(validation_title)

        self.import_issues.setMinimumHeight(150)
        self.import_issues.setStyleSheet(
            "background-color: white;"
            "border: 1px solid #CAD6E3;"
            "border-radius: 7px;"
            "padding: 10px;"
        )
        validation_column.addWidget(self.import_issues)

        result_column = QVBoxLayout()
        result_title = QLabel("Resultado da importa\u00e7\u00e3o")
        result_title.setObjectName("sectionTitle")
        result_column.addWidget(result_title)

        self.import_result = QPlainTextEdit()
        self.import_result.setReadOnly(True)
        self.import_result.setFixedHeight(150)
        self.import_result.setPlaceholderText(
            "Nenhuma importa\u00e7\u00e3o executada nesta sess\u00e3o."
        )
        result_column.addWidget(self.import_result)

        results = QHBoxLayout()
        results.setSpacing(12)
        results.addLayout(validation_column, 1)
        results.addLayout(result_column, 1)

        self.import_panel = ImportWorkflowPanel(
            steps=self.import_steps,
            file_display=self.import_summary,
            results_layout=results,
            preview=self.import_preview,
        )
        import_layout.addWidget(self.import_panel)

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
        self.table.setMinimumHeight(210)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.empty_state = QLabel("Nenhuma Meta cadastrada para os filtros selecionados.")
        self.empty_state.setObjectName("pageDescription")
        self.status = QLabel("Meta x Realizado pronto.")
        self.status.setObjectName("operationStatus")
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addWidget(filter_panel)
        layout.addLayout(cards)
        layout.addWidget(self.empty_state)
        layout.addWidget(self.table, 1)
        layout.addWidget(self.status)
        layout.addWidget(import_area)
        # Scroll only the Meta x Realizado operational tab.
        self.operational_scroll_area = QScrollArea()
        self.operational_scroll_area.setObjectName('metasScrollArea')
        self.operational_scroll_area.setWidgetResizable(True)
        self.operational_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.operational_scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.operational_scroll_area.setWidget(operational)
        self.tabs.addTab(self.operational_scroll_area, "Meta x Realizado")
        self.ranking_tab = QWidget()
        ranking_layout = QVBoxLayout(self.ranking_tab)
        ranking_filters = QHBoxLayout()
        self.ranking_year = WheelBlockedComboBox()
        self.ranking_year.setEnabled(False)
        self.ranking_quarter = WheelBlockedComboBox()
        for quarter in range(1, 5):
            self.ranking_quarter.addItem(f"{quarter}º Trimestre", quarter)
        self.ranking_refresh = QPushButton("Atualizar ranking")
        self.ranking_refresh.setEnabled(False)
        self.ranking_refresh.setProperty("buttonRole", "info")
        self.ranking_entity = EntityMultiSelectCombo()
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

    def set_import_available(self, available: bool) -> None:
        self._import_available = bool(available)
        permitted = getattr(self, "_import_write_allowed", True)
        self.import_steps.set_stage_enabled(
            1, self._import_available and permitted
        )
        if not available:
            for stage in (2, 3, 4):
                self.import_steps.set_stage_enabled(stage, False)
            self.import_summary.setText(
                "Importação central disponível somente no modo servidor."
            )


    def show_import_validation(self, value: dict) -> None:
        metadata = value.get("metadata", {})
        totals = value.get("totals", {})
        self.import_summary.setText(
            f"Arquivo: {metadata.get('file_name', '—')} | "
            f"Tipo: {metadata.get('detected_type', '—')} | "
            f"Ano: {metadata.get('year') or '—'} | "
            f"Registros: {totals.get('rows', 0)} | "
            f"Meta: {format_currency(totals.get('target', 0))} | "
            f"Realizado: {format_currency(totals.get('actual', 0))}"
        )
        rows = value.get("preview", [])
        self.import_preview.setRowCount(min(len(rows), 500))
        for index, row in enumerate(rows[:500]):
            values = (
                row.get("line", "—"),
                f"{row.get('entity_code', '—')} — {row.get('entity_name') or 'Não cadastrada'}",
                f"{row.get('month', 0):02d}/{row.get('year', '—')}",
                row.get("indicator", "—"),
                format_currency(row.get("target", 0)),
                format_currency(row.get("actual", 0)),
            )
            for column, text in enumerate(values):
                self.import_preview.setItem(index, column, QTableWidgetItem(str(text)))
        messages = [f"ERRO: {item}" for item in value.get("errors", [])]
        messages.extend(f"AVISO: {item}" for item in value.get("warnings", []))
        self.import_issues.setText("\n".join(messages) or "Nenhuma inconsistência.")
        self.import_preview.resizeColumnsToContents()
        self.set_status(
            "Arquivo validado e pronto para importação."
            if value.get("can_import") else
            "Arquivo com inconsistências bloqueantes.",
            error=not value.get("can_import"),
        )

    def show_import_result(self, value: dict) -> None:
        self.import_result.setPlainText(
            f"Registros importados: {value.get('imported', 0)}\n"
            f"Ano: {value.get('year') or '-'}\n"
            f"Meta: {format_currency(value.get('target_total', 0))}\n"
            f"Realizado: {format_currency(value.get('actual_total', 0))}"
        )
        self.import_summary.setText(
            f"Importação concluída: {value.get('imported', 0)} registros | "
            f"Ano: {value.get('year') or '—'} | "
            f"Meta: {format_currency(value.get('target_total', 0))} | "
            f"Realizado: {format_currency(value.get('actual_total', 0))}"
        )
        self.set_status("Metas importadas com sucesso.")

    @staticmethod
    def _card(title: str, layout: QHBoxLayout, initial: str = "R$ 0,00") -> QLabel:
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
        selected = self.entity_filter.selected_ids()
        self.entity_filter.set_entities(entities, selected)

    def selected_filters(self) -> tuple[int, int, str, tuple[int, ...] | None]:
        return (
            self.year_filter.currentData(), self.month_filter.currentData(),
            self.indicator_filter.currentData(), self.entity_filter.selected_ids(),
        )

    def set_available_years(
        self, target_years: list[int], ranking_years: list[int]
    ) -> None:
        target = populate_year_combo(self.year_filter, target_years)
        ranking = populate_year_combo(self.ranking_year, ranking_years)
        self.filter_button.setEnabled(target is not None)
        self.ranking_refresh.setEnabled(ranking is not None)
        if target is None:
            self.set_status("Nenhum ano de Metas ou Associação disponível.", error=True)

    def show_result(self, result: TargetVsActual) -> None:
        self.table.setRowCount(len(result.comparisons))
        for row, comparison in enumerate(result.comparisons):
            values = [
                str(comparison.entity_code), comparison.entity_name,
                comparison.indicator.title(), self.currency(comparison.target),
                self.currency(comparison.actual), self.currency(comparison.difference),
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
        self.target_total.setText(self.currency(summary.target_total))
        self.actual_total.setText(self.currency(summary.actual_total))
        self.difference_total.setText(self.currency(summary.difference_total))
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
        selected = self.ranking_entity.selected_ids()
        self.ranking_entity.set_options(
            (
                (f"{row.entity_code} — {row.entity_name}", int(row.entity_id))
                for row in rows
            ),
            selected,
        )
        selected_ids = self.ranking_entity.selected_ids()
        selected_set = None if selected_ids is None else set(selected_ids)
        visible = [
            row
            for row in rows
            if selected_set is None or row.entity_id in selected_set
        ]
        self.ranking_table.setRowCount(len(visible))
        for row_index, row in enumerate(visible):
            situation = "Classificada" if row.classified else "Desclassificada"
            if row.technical_tie:
                situation += " — empate técnico"
            if row.strategy_year == 2025:
                position = " / ".join(
                    f"{result.label}: {result.position}º"
                    for result in row.category_results
                ) or "-"
                billing_points = capture_points = cancellation_points = score = "-"
            else:
                position = row.position or "-"
                billing_points = row.billing_points
                capture_points = row.capture_points
                cancellation_points = row.cancellation_points
                score = row.score
            values = [position, row.entity_code, row.entity_name,
                      self.currency(row.target_total), self.currency(row.actual_total),
                      self.percentage(row.achievement), self.integer(row.captures),
                      self.integer(row.cancellations), billing_points,
                      capture_points, cancellation_points, score,
                      situation, self.currency(row.award) if row.award is not None else "-"]
            for column, value in enumerate(values):
                self.ranking_table.setItem(row_index, column, QTableWidgetItem(str(value)))
        if rows and rows[0].strategy_year == 2025:
            champion_lines = [
                f"{result.label} — {row.entity_name} — {self.currency(result.award)}"
                for row in rows
                for result in row.category_results
                if result.award is not None
            ]
        else:
            champion_lines = [
                f"{row.position}º lugar — {row.entity_name} — {self.currency(row.award)}"
                for row in rows if row.award is not None
            ]
        self.champions.setText(
            "\n".join(champion_lines)
            or "Nenhum campeão definido para o período."
        )
        self.annual_table.setRowCount(len(annual))
        for index, row in enumerate(annual):
            values = [row.entity_code, row.entity_name,
                      *(position or "-" for position in row.positions),
                      row.classified_quarters, row.award_count, self.currency(row.award_total)]
            for column, value in enumerate(values):
                self.annual_table.setItem(index, column, QTableWidgetItem(str(value)))
        detail_id = (
            selected_ids[0]
            if selected_ids is not None and len(selected_ids) == 1
            else None
        )
        detail = next((row for row in rows if row.entity_id == detail_id), None)
        if detail is None:
            detail_text = "Selecione uma Entidade para consultar sua visão detalhada."
        elif detail.strategy_year == 2025:
            rankings = " | ".join(
                f"{result.label}: {result.position}º"
                for result in detail.category_results
            ) or "Sem classificação"
            detail_text = (
                f"Total: {self.currency(detail.target_total)} / {self.currency(detail.actual_total)}  •  "
                f"Atingimento: {self.percentage(detail.achievement)}  •  "
                f"Crescimento de associados: {self.percentage(detail.association_growth_percentage)}  •  "
                f"Ticket médio: {self.currency(detail.average_ticket) if detail.average_ticket is not None else '-'}  •  "
                f"{rankings}  •  Premiação: {self.currency(detail.award) if detail.award else '-'}"
            )
        else:
            detail_text = (
                f"Consultas: Meta {self.currency(detail.meta_queries)} | Realizado {self.currency(detail.actual_queries)}  •  "
                f"Registros: Meta {self.currency(detail.meta_registrations)} | Realizado {self.currency(detail.actual_registrations)}  •  "
                f"Total: {self.currency(detail.target_total)} / {self.currency(detail.actual_total)}  •  "
                f"Atingimento: {self.percentage(detail.achievement)}  •  Captações: {self.integer(detail.captures)}  •  "
                f"Cancelamentos: {self.integer(detail.cancellations)}  •  Pontos: {detail.billing_points}+{detail.capture_points}+{detail.cancellation_points}={detail.score}  •  "
                f"Posição: {detail.position or '-'}  •  Premiação: {self.currency(detail.award) if detail.award else '-'}"
            )
        self.entity_detail.setText(detail_text)
        self.ranking_table.resizeColumnsToContents()

    @staticmethod
    def currency(value: Decimal) -> str:
        return format_currency(value)

    @staticmethod
    def number(value: Decimal) -> str:
        return format_number(value)

    @staticmethod
    def integer(value: Decimal | int) -> str:
        return format_integer(value)

    @staticmethod
    def percentage(value: Decimal | None) -> str:
        return format_percentage(value)
