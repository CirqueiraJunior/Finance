from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from app.api_client import APIClient
from finance_server.security import PASSWORD_POLICY_MESSAGE, validate_password


class InitialSetupDialog(QDialog):
    def __init__(self, client: APIClient, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("Finance — Configuração inicial")
        self.setModal(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel("Configuração inicial do Finance")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        description = QLabel(
            "Cadastre o primeiro administrador para concluir a configuração "
            "do Finance."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QFormLayout()
        self.name = QLineEdit()
        self.email = QLineEdit()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirmation = QLineEdit()
        self.confirmation.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Nome", self.name)
        form.addRow("E-mail", self.email)
        form.addRow("Usuário", self.username)
        form.addRow("Senha", self.password)
        form.addRow("Confirmar senha", self.confirmation)
        layout.addLayout(form)

        policy = QLabel(PASSWORD_POLICY_MESSAGE)
        policy.setWordWrap(True)
        policy.setStyleSheet("color: #4A5568;")
        layout.addWidget(policy)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.conclude_button = buttons.addButton(
            "Concluir", QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.accepted.connect(self._complete)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _complete(self) -> None:
        values = {
            "nome": self.name.text().strip(),
            "email": self.email.text().strip(),
            "username": self.username.text().strip(),
            "password": self.password.text(),
        }
        if not all(values.values()):
            QMessageBox.warning(
                self, "Configuração inicial", "Preencha todos os campos."
            )
            return
        if self.password.text() != self.confirmation.text():
            QMessageBox.warning(
                self,
                "Configuração inicial",
                "A confirmação da senha não confere.",
            )
            return
        try:
            validate_password(self.password.text())
            self.client.create_initial_administrator(values)
        except (RuntimeError, ValueError) as error:
            QMessageBox.warning(self, "Configuração inicial", str(error))
            return

        QMessageBox.information(
            self,
            "Configuração concluída",
            "O Finance foi configurado com sucesso.",
        )
        self.accept()
