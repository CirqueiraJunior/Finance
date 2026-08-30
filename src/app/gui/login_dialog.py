from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QVBoxLayout,
)

from app.api_client import APIClient
from app.api_client.client import AuthenticatedUser


class LoginDialog(QDialog):
    def __init__(self, client: APIClient, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.user: AuthenticatedUser | None = None
        self.setWindowTitle("Finance — Acesso")
        self.setModal(True)
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        title = QLabel("FINANCE")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        form = QFormLayout()
        self.identifier = QLineEdit()
        self.identifier.setPlaceholderText("Usuário ou e-mail")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Usuário", self.identifier)
        form.addRow("Senha", self.password)
        layout.addLayout(form)
        forgot = QPushButton("Esqueci minha senha")
        forgot.clicked.connect(self._forgot)
        layout.addWidget(forgot)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.enter_button = buttons.addButton("Entrar", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self._login)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.password.returnPressed.connect(self._login)

    def _login(self) -> None:
        self.enter_button.setEnabled(False)
        try:
            self.user = self.client.login(self.identifier.text().strip(), self.password.text())
        except RuntimeError as error:
            QMessageBox.warning(self, "Acesso não autorizado", str(error))
        else:
            self.accept()
        finally:
            self.enter_button.setEnabled(True)

    def _forgot(self) -> None:
        email = self.identifier.text().strip()
        if "@" not in email:
            QMessageBox.information(self, "Recuperar senha", "Informe seu e-mail no campo Usuário.")
            return
        try:
            message = self.client.forgot_password(email)
        except RuntimeError as error:
            QMessageBox.warning(self, "Recuperar senha", str(error))
        else:
            QMessageBox.information(self, "Recuperar senha", message)
