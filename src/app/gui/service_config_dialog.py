from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.core.branding import apply_window_icon
from finance_server.environment import EnvironmentCommandError
from finance_server.service_setup import provision_service_configuration


class ServiceConfigurationDialog(QDialog):
    """One-time secure provisioning used only by the elevated installer."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Finance â€” ConfiguraÃ§Ã£o do servidor")
        self.setModal(True)
        self.setMinimumWidth(520)
        apply_window_icon(self)

        title = QLabel("ConfiguraÃ§Ã£o segura do servidor")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Informe a conexÃ£o PostgreSQL utilizada pelo Finance. A senha serÃ¡ "
            "protegida pelo Windows e nÃ£o serÃ¡ armazenada em texto aberto."
        )
        description.setWordWrap(True)

        self.host = QLineEdit()
        self.host.setPlaceholderText("Servidor PostgreSQL")
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(5432)
        self.database = QLineEdit("postgres")
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow("Host:", self.host)
        form.addRow("Porta:", self.port)
        form.addRow("Banco:", self.database)
        form.addRow("UsuÃ¡rio:", self.username)
        form.addRow("Senha:", self.password)

        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.clicked.connect(self.reject)
        self.save_button = QPushButton("Salvar configuraÃ§Ã£o")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)

        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addLayout(form)
        layout.addLayout(actions)

    def _save(self) -> None:
        self.save_button.setEnabled(False)
        try:
            provision_service_configuration(
                host=self.host.text(),
                port=self.port.value(),
                database=self.database.text(),
                username=self.username.text(),
                password=self.password.text(),
            )
        except (EnvironmentCommandError, OSError, ValueError) as error:
            QMessageBox.critical(self, "ConfiguraÃ§Ã£o do servidor", str(error))
            self.save_button.setEnabled(True)
            return

        self.password.clear()
        QMessageBox.information(
            self,
            "ConfiguraÃ§Ã£o do servidor",
            "ConfiguraÃ§Ã£o protegida salva com sucesso.",
        )
        self.accept()
