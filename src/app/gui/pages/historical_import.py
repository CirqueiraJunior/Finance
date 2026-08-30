from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app.importers.historical_importer import HistoricalPreview


class HistoricalImportDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Importação histórica controlada")
        self.resize(850, 600)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        file_row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.choose_button = QPushButton("Selecionar arquivo")
        file_row.addWidget(self.file_path, 1)
        file_row.addWidget(self.choose_button)
        form.addRow("Arquivo", file_row)
        self.requested_type = QComboBox()
        self.requested_type.addItem("Detectar automaticamente", None)
        self.requested_type.addItem("Associação", "ASSOCIACAO")
        form.addRow("Tipo", self.requested_type)
        layout.addLayout(form)
        self.analyze_button = QPushButton("Analisar e gerar preview")
        layout.addWidget(self.analyze_button)
        self.summary = QLabel("Selecione um arquivo para iniciar.")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(
            ["Linha", "Período", "Referência", "Valor", "Situação"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)
        self.issues = QLabel()
        self.issues.setWordWrap(True)
        layout.addWidget(self.issues)
        actions = QHBoxLayout()
        actions.addStretch()
        self.cancel_button = QPushButton("Cancelar")
        self.import_button = QPushButton("Importar")
        self.import_button.setEnabled(False)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.import_button)
        layout.addLayout(actions)
        self.choose_button.clicked.connect(self.choose_file)
        self.cancel_button.clicked.connect(self.reject)

    def choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar planilha oficial", "",
            "Planilhas Excel (*.xlsx *.xlsm)",
        )
        if path:
            self.file_path.setText(path)
            self.import_button.setEnabled(False)

    def show_preview(self, preview: HistoricalPreview) -> None:
        self.summary.setText(
            f"Tipo detectado: {preview.detected_type} | Ano: {preview.year or '—'} | "
            f"Linhas: {len(preview.rows)} | Válidas: {preview.valid_rows} | "
            f"Duplicidades: {preview.duplicates} | Total: {preview.total}"
        )
        self.table.setRowCount(min(len(preview.rows), 500))
        for index, row in enumerate(preview.rows[:500]):
            reference = row.get("description") or row.get("code") or row.get("source_label") or "—"
            period = (f"{row.get('month', 0):02d}/{row.get('year')}"
                      if row.get("month") else str(row.get("year") or "—"))
            if "capture" in row:
                value = (f"Captação: {row['capture']} | "
                         f"Cancelamento: {row.get('cancellation', 0)} | "
                         f"Total: {row.get('execution', 0)}")
            else:
                value = row.get("value") or row.get("target") or "—"
            situation = ("Duplicado" if row.get("duplicate") else
                         "Atualização" if row.get("update") else "Válido")
            values = (row.get("line", "—"), period, reference, value, situation)
            for column, value in enumerate(values):
                self.table.setItem(index, column, QTableWidgetItem(str(value)))
        messages = [f"ERRO: {item}" for item in preview.errors]
        messages.extend(f"AVISO: {item}" for item in preview.warnings)
        self.issues.setText("\n".join(messages[:20]) or "Nenhuma inconsistência.")
        self.import_button.setEnabled(preview.can_import)

    def show_report(self, report) -> None:
        self.summary.setText(
            f"Importação concluída. Processados: {report.processed} | "
            f"Importados: {report.imported} | Ignorados: {report.ignored} | "
            f"Duplicados: {report.duplicates} | Warnings: {report.warnings} | "
            f"Erros: {report.errors} | Total reconciliado: {report.total} | "
            f"Backup: {report.backup_path}"
        )
        self.import_button.setEnabled(False)
