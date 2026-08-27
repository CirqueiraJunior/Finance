from datetime import date
from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.report_service import AnnualReport


class RelatoriosPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("contentPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(12)

        title = QLabel("Relatórios e Exportações")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Relatório financeiro anual e geração dos cinco CSVs oficiais do site CESPC/GO."
        )
        description.setObjectName("pageDescription")

        filters = QHBoxLayout()
        self.year_filter = QSpinBox()
        self.year_filter.setRange(2000, 9999)
        self.year_filter.setValue(date.today().year)
        self.refresh_button = QPushButton("Atualizar relatório")
        self.refresh_button.setObjectName("primaryButton")
        filters.addWidget(QLabel("Ano"))
        filters.addWidget(self.year_filter)
        filters.addWidget(self.refresh_button)
        filters.addStretch()

        self.report_table = QTableWidget(0, 10)
        self.report_table.setHorizontalHeaderLabels(
            [
                "Mês", "Receita", "Despesa", "Resultado", "Aplicações",
                "Resgates", "Mov. Caixa", "Saldo Aplicado", "BOE", "Resultado Orçado",
            ]
        )
        self.report_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.report_table.horizontalHeader().setStretchLastSection(True)

        export_title = QLabel("Exportação CSV CESPC/GO")
        export_title.setObjectName("sectionTitle")
        export_actions = QHBoxLayout()
        self.destination_label = QLabel("Pasta não selecionada")
        self.choose_folder_button = QPushButton("Selecionar pasta")
        self.validate_button = QPushButton("Validar CSVs")
        self.export_button = QPushButton("Gerar 5 CSVs")
        self.export_button.setObjectName("primaryButton")
        export_actions.addWidget(self.destination_label, 1)
        export_actions.addWidget(self.choose_folder_button)
        export_actions.addWidget(self.validate_button)
        export_actions.addWidget(self.export_button)

        self.export_output = QPlainTextEdit()
        self.export_output.setReadOnly(True)
        self.export_output.setMaximumHeight(150)
        self.export_output.setPlaceholderText(
            "A validação verifica os 12 meses de Meta/Realizado e Associação "
            "para todas as Entidades ativas."
        )
        self.status = QLabel("Relatórios prontos.")
        self.status.setObjectName("operationStatus")

        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(filters)
        layout.addWidget(self.report_table, 1)
        layout.addWidget(export_title)
        layout.addLayout(export_actions)
        layout.addWidget(self.export_output)
        layout.addWidget(self.status)

        self._destination: Path | None = None

    def selected_year(self) -> int:
        return self.year_filter.value()

    def choose_destination(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Pasta de exportação")
        if selected:
            self._destination = Path(selected)
            self.destination_label.setText(selected)

    def destination(self) -> Path | None:
        return self._destination

    def show_report(self, report: AnnualReport) -> None:
        self.report_table.setRowCount(len(report.rows))
        for row_index, row in enumerate(report.rows):
            values = [
                f"{row.month:02d}",
                self.currency(row.total_revenue),
                self.currency(row.total_expense),
                self.currency(row.operational_result),
                self.currency(row.applications),
                self.currency(row.redemptions),
                self.currency(row.cash_movement),
                self.currency(row.applied_balance),
                self.currency(row.boe_value),
                self.currency(row.budgeted_result),
            ]
            for column, value in enumerate(values):
                self.report_table.setItem(row_index, column, QTableWidgetItem(value))
        self.report_table.resizeColumnsToContents()

    def show_export_message(self, message: str) -> None:
        self.export_output.setPlainText(message)

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status.setText(message)
        self.status.setProperty("error", error)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    @staticmethod
    def currency(value) -> str:
        formatted = f"{value:,.4f}".replace(",", "_").replace(".", ",").replace("_", ".")
        return f"R$ {formatted}"
