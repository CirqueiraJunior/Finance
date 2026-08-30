from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
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

from app.importers.boe_types import BOEValidationResult
from app.models.boe_import import BOEImport
from app.services.boe_service import BOEImportDetails


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
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(14)

        self.scroll_area.setWidget(content)
        outer_layout.addWidget(self.scroll_area)

        title = QLabel("Faturamento BOE")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Valide e importe o resumo mensal por Entidade da aba Taxa BOE."
        )
        description.setObjectName("pageDescription")

        file_layout = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setObjectName("boeFilePath")
        self.file_path.setReadOnly(True)
        self.file_path.setPlaceholderText("Selecione um arquivo BOE no formato .xlsx")
        self.select_button = QPushButton("Selecionar arquivo")
        self.select_button.setObjectName("primaryButton")
        file_layout.addWidget(self.file_path, 1)
        file_layout.addWidget(self.select_button)

        action_layout = QHBoxLayout()
        self.validate_button = QPushButton("Validar")
        self.validate_button.setEnabled(False)
        self.import_button = QPushButton("Importar")
        self.import_button.setObjectName("primaryButton")
        self.import_button.setEnabled(False)
        action_layout.addWidget(self.validate_button)
        action_layout.addWidget(self.import_button)
        action_layout.addStretch()

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

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(file_layout)
        layout.addLayout(action_layout)
        layout.addLayout(result_layout)
        layout.addWidget(history_label)
        layout.addWidget(self.history_table)
        layout.addWidget(details_label)
        layout.addWidget(self.details_state)
        layout.addLayout(summary_layout)
        layout.addWidget(self.details_table)
        layout.addWidget(self.operation_status)

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
    def _format_currency(value: Decimal, decimals: int = 2) -> str:
        formatted = f"{value:,.{decimals}f}"
        return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")

    @staticmethod
    def _format_integer(value: int) -> str:
        return f"{value:,}".replace(",", ".")
