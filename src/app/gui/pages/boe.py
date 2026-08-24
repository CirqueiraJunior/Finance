from decimal import Decimal

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.importers.boe_types import BOEValidationResult
from app.models.boe_import import BOEImport


class BoePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

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

        result_label = QLabel("Resultado da validação")
        result_label.setObjectName("sectionTitle")
        self.validation_result = QPlainTextEdit()
        self.validation_result.setObjectName("boeValidationResult")
        self.validation_result.setReadOnly(True)
        self.validation_result.setMaximumHeight(160)

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

        self.operation_status = QLabel("Selecione um arquivo para iniciar.")
        self.operation_status.setObjectName("operationStatus")

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(file_layout)
        layout.addLayout(action_layout)
        layout.addWidget(result_label)
        layout.addWidget(self.validation_result)
        layout.addWidget(history_label)
        layout.addWidget(self.history_table, 1)
        layout.addWidget(self.operation_status)

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

    def show_history(self, imports: list[BOEImport]) -> None:
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
                self.history_table.setItem(row, column, QTableWidgetItem(value))
        self.history_table.resizeColumnsToContents()

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.operation_status.setText(message)
        self.operation_status.setProperty("error", error)
        self.operation_status.style().unpolish(self.operation_status)
        self.operation_status.style().polish(self.operation_status)

    @staticmethod
    def _format_currency(value: Decimal) -> str:
        formatted = f"{value:,.2f}"
        return "R$ " + formatted.replace(",", "_").replace(".", ",").replace("_", ".")
