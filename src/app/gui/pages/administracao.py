from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.services.administration_service import SystemInformation


class AdministracaoPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Administração")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        info_widget = QWidget()
        info = QFormLayout(info_widget)
        self.fields = {key: QLabel("—") for key in (
            "application", "environment", "version", "database", "revision",
            "logs", "entities", "entries", "boe", "targets",
        )}
        for label, key in (
            ("Aplicação", "application"), ("Ambiente", "environment"),
            ("Versão", "version"), ("Banco utilizado", "database"),
            ("Revisão Alembic", "revision"), ("Diretório de logs", "logs"),
            ("Entidades", "entities"), ("Lançamentos", "entries"),
            ("Imports BOE", "boe"), ("Metas", "targets"),
        ):
            self.fields[key].setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            info.addRow(label, self.fields[key])
        layout.addWidget(info_widget)
        actions = QHBoxLayout()
        self.refresh_button = QPushButton("Consultar informações")
        self.logs_button = QPushButton("Abrir diretório de logs")
        self.backup_button = QPushButton("Fazer Backup")
        self.import_button = QPushButton("Importação histórica")
        for button in (self.refresh_button, self.logs_button,
                       self.backup_button, self.import_button):
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addWidget(QLabel("Histórico de exportações CSV"))
        self.exports = QTableWidget(0, 3)
        self.exports.setHorizontalHeaderLabels(["Data", "Ano", "Diretório"])
        self.exports.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.exports)
        server_actions = QHBoxLayout()
        self.server_button = QPushButton("Status do servidor")
        self.users_button = QPushButton("Usuários")
        self.audit_button = QPushButton("Auditoria")
        for button in (self.server_button, self.users_button, self.audit_button):
            server_actions.addWidget(button)
        server_actions.addStretch()
        layout.addLayout(server_actions)
        self.multiuser_table = QTableWidget(0, 4)
        self.multiuser_table.setHorizontalHeaderLabels(["ID/Data", "Nome/Usuário", "Perfil/Ação", "Estado/Módulo"])
        self.multiuser_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.multiuser_table)
        self.status = QLabel()
        layout.addWidget(self.status)

    def show_information(self, value: SystemInformation) -> None:
        values = {
            "application": value.application, "environment": value.environment,
            "version": value.version, "database": value.database,
            "revision": value.alembic_revision, "logs": str(value.log_directory),
            "entities": value.entities, "entries": value.entries,
            "boe": value.boe_imports, "targets": value.targets,
        }
        for key, text in values.items():
            self.fields[key].setText(str(text))
        self.exports.setRowCount(len(value.exports))
        for row, export in enumerate(value.exports):
            for column, text in enumerate((
                export.created_at.strftime("%d/%m/%Y %H:%M") if export.created_at else "—",
                export.ano, export.diretorio,
            )):
                self.exports.setItem(row, column, QTableWidgetItem(str(text)))
        self.exports.resizeColumnsToContents()

    def show_remote_information(self, health: dict) -> None:
        unavailable = "Não informado pela API"
        values = {
            "application": "Finance API",
            "environment": "Servidor central",
            "version": health.get("version", unavailable),
            "database": "PostgreSQL central",
            "revision": unavailable,
            "logs": "Indisponível no modo servidor",
            "entities": unavailable,
            "entries": unavailable,
            "boe": unavailable,
            "targets": unavailable,
        }
        for key, text in values.items():
            self.fields[key].setText(str(text))
        self.exports.setRowCount(0)

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #b91c1c;" if error else "color: #166534;")

    def show_remote_rows(self, rows: list[tuple[str, str, str, str]]) -> None:
        self.multiuser_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                self.multiuser_table.setItem(row, column, QTableWidgetItem(value))
        self.multiuser_table.resizeColumnsToContents()
