from app.widgets.wheel_guard import WheelBlockedComboBox, WheelBlockedDateEdit
from decimal import Decimal

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit, QScrollArea,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.import_workflow_steps import ImportWorkflowSteps
from app.gui.import_workflow_panel import ImportWorkflowPanel
from app.gui.formatters import format_currency, format_integer
from app.importers.boe_types import BOEValidationResult
from app.models.boe_import import BOEImport
from app.services.boe_service import (
    BOEImportDetails,
    BOEOperationalEntityOption,
    BOEOperationalSummary,
)
from app.widgets.entity_multi_select import EntityMultiSelectCombo


class BOEPeriodEdit(WheelBlockedDateEdit):
    """Seletor de período que não altera o valor por rolagem acidental."""

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API
        event.ignore()


class BoePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.setSpacing(0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("boeScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("boeScrollContent")

        layout = QVBoxLayout(content)
        layout.setContentsMargins(32, 2, 32, 12)
        layout.setSpacing(6)

        self.scroll_area.setWidget(content)
        outer_layout.addWidget(self.scroll_area)

        title = QLabel("Faturamento BOE")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Valide e importe o resumo mensal por Entidade da aba Taxa BOE."
        )
        description.setObjectName("pageDescription")

        self.file_path = QLineEdit()
        self.file_path.setObjectName("boeFilePath")
        self.file_path.setReadOnly(True)
        self.file_path.setPlaceholderText("Selecione um arquivo BOE no formato .xlsx")


        result_layout = QHBoxLayout()
        result_layout.setSpacing(12)

        validation_layout = QVBoxLayout()
        result_label = QLabel("Resultado da validação")
        result_label.setObjectName("sectionTitle")
        self.validation_result = QPlainTextEdit()
        self.validation_result.setObjectName("boeValidationResult")
        self.validation_result.setReadOnly(True)
        self.validation_result.setMinimumHeight(115)
        self.validation_result.setMaximumHeight(150)
        validation_layout.addWidget(result_label)
        validation_layout.addWidget(self.validation_result)
        result_layout.addLayout(validation_layout, 1)

        import_layout = QVBoxLayout()
        import_result_label = QLabel("Resultado da importação")
        import_result_label.setObjectName("sectionTitle")
        self.import_result = QPlainTextEdit()
        self.import_result.setObjectName("boeImportResult")
        self.import_result.setReadOnly(True)
        self.import_result.setMinimumHeight(115)
        self.import_result.setMaximumHeight(150)
        self.import_result.setPlaceholderText(
            "Nenhuma importação executada nesta sessão."
        )
        import_layout.addWidget(import_result_label)
        import_layout.addWidget(self.import_result)
        result_layout.addLayout(import_layout, 1)

        self.validation_issues_label = QLabel(
            "Inconsist\u00eancias da valida\u00e7\u00e3o"
        )
        self.validation_issues_label.setObjectName("sectionTitle")
        self.validation_issues = QTableWidget(0, 4)
        self.validation_issues.setObjectName("boeValidationIssuesTable")
        self.validation_issues.setHorizontalHeaderLabels([
            "Severidade", "Linha", "C\u00f3digo", "Descri\u00e7\u00e3o"
        ])
        self.validation_issues.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.validation_issues.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.validation_issues.setMinimumHeight(190)
        self.validation_issues.setMaximumHeight(320)
        self.validation_issues.horizontalHeader().setStretchLastSection(True)
        self.validation_issues_label.hide()
        self.validation_issues.hide()

        history_label = QLabel("Histórico de importações")
        history_label.setObjectName("sectionTitle")
        self.history_table = QTableWidget(0, 6)
        self.history_table.setObjectName("boeHistoryTable")
        self.history_table.setHorizontalHeaderLabels(
            ["Período", "Arquivo", "Entidades", "Inconsistências", "Valor", "Status"]
        )
        self.history_table.horizontalHeader().setStretchLastSection(True)
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.history_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.history_table.setMinimumHeight(220)
        self.history_table.setMaximumHeight(320)

        operations_label = QLabel("Consulta operacional BOE")
        operations_label.setObjectName("sectionTitle")
        filter_panel = QWidget()
        filter_panel.setObjectName("dashboardFilterBar")
        filters_layout = QHBoxLayout(filter_panel)
        self.year_filter = WheelBlockedComboBox()
        self.year_filter.setObjectName("boeYearFilter")
        self.month_filter = WheelBlockedComboBox()
        self.month_filter.setObjectName("boeMonthFilter")
        self._imported_periods = set()
        self.year_filter.currentIndexChanged.connect(
            self._update_available_months
        )
        self.entity_filter = EntityMultiSelectCombo(all_label="Todas")
        self.entity_filter.setObjectName("boeEntityFilter")
        self.query_button = QPushButton("Aplicar filtro")
        self.query_button.setProperty("buttonRole", "info")
        self.query_button.setEnabled(False)
        self.query_button.setObjectName("primaryButton")
        for label_text, widget in (
            ("Ano", self.year_filter),
            ("M\u00eas", self.month_filter),
            ("Entidade", self.entity_filter),
        ):
            field = QVBoxLayout()
            field.addWidget(QLabel(label_text))
            field.addWidget(widget)
            filters_layout.addLayout(field, 1)
        filters_layout.addWidget(self.query_button, alignment=Qt.AlignmentFlag.AlignBottom)

        operational_kpis = QHBoxLayout()
        self.operational_queries = self._create_summary_card(operational_kpis, "Consultas", "0")
        self.operational_unit_value = self._create_summary_card(
            operational_kpis, "Valor Unitário", self._format_currency(Decimal("0.0000"))
        )
        self.operational_total_value = self._create_summary_card(
            operational_kpis, "Valor Total Pago", self._format_currency(Decimal("0.0000"))
        )
        self.operations_table = QTableWidget(0, 5)
        self.operations_table.setObjectName("boeOperationsTable")
        self.operations_table.setHorizontalHeaderLabels(
            ["Período", "Entidade", "Consultas", "Valor Unitário", "Valor Total"]
        )
        self.operations_table.horizontalHeader().setStretchLastSection(True)
        self.operations_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.operations_table.setMinimumHeight(240)

        details_label = QLabel("Detalhamento por Entidade")
        details_label.setObjectName("sectionTitle")
        self.details_state = QLabel(
            "Selecione uma importação para visualizar o detalhamento por Entidade."
        )
        self.details_state.setObjectName("pageDescription")

        summary_layout = QHBoxLayout()
        self.entities_total = self._create_summary_card(
            summary_layout, "Entidades", "0"
        )
        self.queries_total = self._create_summary_card(
            summary_layout, "Consultas", "0"
        )
        self.value_total = self._create_summary_card(
            summary_layout, "Valor Total", self._format_currency(Decimal("0.0000"))
        )

        self.details_table = QTableWidget(0, 4)
        self.details_table.setObjectName("boeDetailsTable")
        self.details_table.setHorizontalHeaderLabels(
            ["Código", "Entidade", "Consultas", "Valor do Repasse"]
        )
        self.details_table.horizontalHeader().setStretchLastSection(True)
        self.details_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.details_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.details_table.setMinimumHeight(320)

        self.operation_status = QLabel("Selecione um arquivo para iniciar.")
        self.operation_status.setObjectName("operationStatus")

        self.import_steps = ImportWorkflowSteps(steps=(
            "Selecionar",
            "Validar",
            "Comparar e autorizar",
            "Importar",
        ))
        layout.addWidget(title)
        layout.addWidget(description)

        # Filters and operational query first.
        layout.addWidget(operations_label)
        layout.addWidget(filter_panel)
        layout.addLayout(operational_kpis)
        layout.addWidget(self.operations_table)

        # Historical data and entity details.
        layout.addWidget(history_label)
        layout.addWidget(self.history_table)
        layout.addWidget(details_label)
        layout.addWidget(self.details_state)
        layout.addLayout(summary_layout)
        layout.addWidget(self.details_table)

        # Import workflow at the bottom.
        import_section = QLabel("Importa\u00e7\u00e3o BOE")
        import_section.setObjectName("sectionTitle")
        layout.addWidget(import_section)


        self.import_panel = ImportWorkflowPanel(
            steps=self.import_steps,
            file_display=self.file_path,
            results_layout=result_layout,
            preview=self.validation_issues,
        )
        self.import_panel.add_footer(self.operation_status)

        layout.addWidget(self.validation_issues_label)
        layout.addWidget(self.import_panel)

    @staticmethod
    def _create_summary_card(layout: QHBoxLayout, title: str, value: str) -> QLabel:
        card = QWidget()
        card.setObjectName("summaryCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(14, 8, 14, 8)
        label = QLabel(title)
        label.setObjectName("summaryLabel")
        amount = QLabel(value)
        amount.setObjectName("summaryValue")
        card_layout.addWidget(label)
        card_layout.addWidget(amount)
        layout.addWidget(card, 1)
        return amount

    @staticmethod
    def _create_period_edit(value: QDate) -> BOEPeriodEdit:
        edit = BOEPeriodEdit(value)
        edit.setDisplayFormat("MM/yyyy")
        edit.setCalendarPopup(True)
        return edit

    def set_import_periods(self, imports) -> None:
        previous_year = self.year_filter.currentData()
        previous_month = self.month_filter.currentData()
        self._imported_periods = {
            (int(item.periodo_ano), int(item.periodo_mes))
            for item in imports
            if getattr(item, "status", None) == "imported"
            and 1 <= int(item.periodo_mes) <= 12
        }

        self.year_filter.blockSignals(True)
        self.year_filter.clear()
        for year in sorted(
            {year for year, _ in self._imported_periods},
            reverse=True,
        ):
            self.year_filter.addItem(str(year), year)

        index = self.year_filter.findData(previous_year)
        if index >= 0:
            self.year_filter.setCurrentIndex(index)
        self.year_filter.blockSignals(False)

        self._update_available_months()
        index = self.month_filter.findData(previous_month)
        if index >= 0:
            self.month_filter.setCurrentIndex(index)
        self.query_button.setEnabled(bool(self._imported_periods))

    def _update_available_months(self, _index=-1) -> None:
        year = self.year_filter.currentData()
        previous = self.month_filter.currentData()
        self.month_filter.clear()
        if year is None:
            return

        self.month_filter.addItem("Ano completo", None)
        names = (
            "Janeiro", "Fevereiro", "Mar\u00e7o",
            "Abril", "Maio", "Junho", "Julho",
            "Agosto", "Setembro", "Outubro",
            "Novembro", "Dezembro",
        )
        for y, month in sorted(self._imported_periods):
            if y == year:
                self.month_filter.addItem(names[month - 1], month)
        index = self.month_filter.findData(previous)
        if index >= 0:
            self.month_filter.setCurrentIndex(index)

    def operational_filters(self):
        year = self.year_filter.currentData()
        if year is None:
            raise ValueError("Nenhuma competencia BOE disponivel.")

        month = self.month_filter.currentData()
        first = 1 if month is None else int(month)
        last = 12 if month is None else int(month)
        filters = (
            int(year), first, int(year), last,
        )
        selection = self.entity_filter.selected_values()
        if selection is None:
            return (*filters, None)
        if not selection:
            raise ValueError("Selecione ao menos uma Entidade BOE.")
        if any(
            kind not in {"master_entity", "boe_source"}
            for kind, _value in selection
        ):
            raise ValueError("Filtro de Entidade BOE inválido.")
        entity_ids = tuple(
            int(value) for kind, value in selection
            if kind == "master_entity"
        )
        source_codes = tuple(
            int(value) for kind, value in selection
            if kind == "boe_source"
        )
        if len(selection) == 1 and entity_ids:
            return (*filters, entity_ids[0])
        if len(selection) == 1 and source_codes:
            return (*filters, None, source_codes[0])
        return (
            *filters,
            None,
            None,
            entity_ids or None,
            source_codes or None,
        )

    def set_operational_entities(
        self,
        entities: tuple[BOEOperationalEntityOption, ...],
    ) -> None:
        self.entity_filter.set_options(
            (
                (
                    entity.name,
                    (
                        ("boe_source", int(entity.source_code))
                        if entity.source_code is not None
                        else ("master_entity", int(entity.entity_id))
                    ),
                )
                for entity in entities
            )
        )

    def show_operations(self, summary: BOEOperationalSummary) -> None:
        self.operations_table.setRowCount(len(summary.rows))
        for row_index, row in enumerate(summary.rows):
            values = (
                f"{row.month:02d}/{row.year}", row.entity_name,
                self._format_integer(row.queries), self._format_currency(row.unit_value),
                self._format_currency(row.total_value),
            )
            for column, value in enumerate(values):
                self.operations_table.setItem(row_index, column, QTableWidgetItem(value))
        self.operations_table.resizeColumnsToContents()
        self.operational_queries.setText(self._format_integer(summary.total_queries))
        self.operational_unit_value.setText(self._format_currency(summary.unit_value))
        self.operational_total_value.setText(self._format_currency(summary.total_value))

    def show_validation(self, result: BOEValidationResult) -> None:
        status = "APROVADO" if result.aprovado else "REPROVADO"
        period = (
            f"{result.periodo_mes:02d}/{result.periodo_ano}"
            if result.periodo_mes is not None and result.periodo_ano is not None
            else "não identificado"
        )
        lines = [
            f"Status: {status}",
            f"Período: {period}",
            f"Entidades: {len(result.linhas)}",
            f"Erros: {result.quantidade_erros}",
            f"Avisos: {result.quantidade_avisos}",
            f"Valor total: {self._format_currency(result.valor_total_calculado)}",
        ]
        for issue in result.inconsistencias:
            location = f"linha {issue.linha}" if issue.linha is not None else "arquivo"
            code = f", código {issue.codigo}" if issue.codigo else ""
            lines.append(
                f"[{issue.severidade.value}] {location}{code}: {issue.mensagem}"
            )
        self.validation_result.setPlainText("\n".join(lines))
        ordered = sorted(
            result.inconsistencias,
            key=lambda issue: (
                0 if issue.severidade.value == "ERROR" else 1
            ),
        )
        self.validation_issues.setRowCount(len(ordered))
        self.validation_issues_label.show()
        self.validation_issues.show()

        for row, issue in enumerate(ordered):
            values = (
                "Erro" if issue.severidade.value == "ERROR" else "Aviso",
                str(issue.linha) if issue.linha is not None else "Arquivo",
                issue.codigo or "\u2014",
                issue.mensagem,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(issue.mensagem)
                self.validation_issues.setItem(row, column, item)

        self.validation_issues.setColumnWidth(0, 100)
        self.validation_issues.setColumnWidth(1, 70)
        self.validation_issues.setColumnWidth(2, 110)


    def clear_validation_preview(self) -> None:
        self.validation_result.clear()
        self.validation_issues.setRowCount(0)
        self.validation_issues_label.hide()
        self.validation_issues.hide()

    def clear_import_result(self) -> None:
        self.import_result.clear()

    def show_import_success(self, imported: BOEImport) -> None:
        lines = [
            "Status: IMPORTADO COM SUCESSO",
            f"Período: {imported.periodo_mes:02d}/{imported.periodo_ano}",
            f"Arquivo: {imported.nome_arquivo}",
            f"Entidades: {imported.quantidade_entidades}",
            f"Inconsistências: {imported.quantidade_inconsistencias}",
            f"Valor total: {self._format_currency(imported.valor_total)}",
        ]
        self.import_result.setPlainText("\n".join(lines))

    def show_import_error(self, message: str) -> None:
        self.import_result.setPlainText(
            "Status: FALHA NA IMPORTAÇÃO\n"
            f"Mensagem: {message}"
        )

    def show_history(self, imports: list[BOEImport]) -> None:
        self.history_table.clearSelection()
        self.clear_details()
        self.history_table.setRowCount(len(imports))
        for row, item in enumerate(imports):
            values = [
                f"{item.periodo_mes:02d}/{item.periodo_ano}",
                item.nome_arquivo,
                str(item.quantidade_entidades),
                str(item.quantidade_inconsistencias),
                self._format_currency(item.valor_total),
                item.status,
            ]
            for column, value in enumerate(values):
                table_item = QTableWidgetItem(value)
                if column == 0:
                    table_item.setData(Qt.ItemDataRole.UserRole, item.id)
                self.history_table.setItem(row, column, table_item)
        self.history_table.resizeColumnsToContents()
        self.set_import_periods(imports)

    def selected_import_id(self) -> int | None:
        selected = self.history_table.selectedItems()
        if not selected:
            return None
        identifier = self.history_table.item(selected[0].row(), 0).data(
            Qt.ItemDataRole.UserRole
        )
        return int(identifier) if identifier is not None else None

    def clear_details(self, message: str | None = None) -> None:
        self.details_table.setRowCount(0)
        self.entities_total.setText("0")
        self.queries_total.setText("0")
        self.value_total.setText(self._format_currency(Decimal("0.0000")))
        self.details_state.setText(
            message
            or "Selecione uma importação para visualizar o detalhamento por Entidade."
        )

    def show_details(self, details: BOEImportDetails) -> None:
        self.details_table.setRowCount(len(details.entities))
        for row, entity in enumerate(details.entities):
            values = [
                str(entity.code),
                entity.entity_name,
                self._format_integer(entity.queries),
                self._format_currency(entity.value),
            ]
            for column, value in enumerate(values):
                self.details_table.setItem(row, column, QTableWidgetItem(value))
        self.details_table.resizeColumnsToContents()
        self.entities_total.setText(self._format_integer(details.total_entities))
        self.queries_total.setText(self._format_integer(details.total_queries))
        self.value_total.setText(self._format_currency(details.total_value))
        period = details.boe_import
        self.details_state.setText(
            f"Importação {period.periodo_mes:02d}/{period.periodo_ano} — "
            f"{period.nome_arquivo}"
            if details.entities
            else "Nenhum detalhamento por Entidade disponível para esta importação."
        )

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.operation_status.setText(message)
        self.operation_status.setProperty("error", error)
        self.operation_status.style().unpolish(self.operation_status)
        self.operation_status.style().polish(self.operation_status)

    @staticmethod
    def _format_currency(value: Decimal) -> str:
        return format_currency(value)

    @staticmethod
    def _format_integer(value: int) -> str:
        return format_integer(value)
