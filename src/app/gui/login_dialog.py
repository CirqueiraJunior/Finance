from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QGroupBox,
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from app.api_client import APIClient
from app.api_client.client import AuthenticatedUser
from finance_server.security import validate_password


class ChangePasswordDialog(QDialog):
    """Troca voluntária da senha do usuário autenticado."""

    def __init__(self, client: APIClient, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("Alterar senha")
        self.setModal(True)
        self.setMinimumWidth(440)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.current_password = QLineEdit()
        self.current_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password = QLineEdit()
        self.new_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirmation = QLineEdit()
        self.confirmation.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Senha atual", self.current_password)
        form.addRow("Nova senha", self.new_password)
        form.addRow("Confirmar nova senha", self.confirmation)
        layout.addLayout(form)
        layout.addSpacing(12)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Alterar senha")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        if self.new_password.text() != self.confirmation.text():
            QMessageBox.warning(
                self, "Alterar senha", "As senhas informadas não coincidem."
            )
            return
        try:
            validate_password(self.new_password.text())
            self.client.change_password(
                self.current_password.text(), self.new_password.text()
            )
        except (RuntimeError, ValueError) as error:
            QMessageBox.warning(self, "Alterar senha", str(error))
            return
        QMessageBox.information(self, "Alterar senha", "Senha alterada com sucesso.")
        self.accept()


class RequiredPasswordChangeDialog(QDialog):
    def __init__(self, client: APIClient, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.user: AuthenticatedUser | None = None
        self.setWindowTitle("Defina sua nova senha")
        self.setModal(True)
        self.setMinimumWidth(440)
        layout = QVBoxLayout(self)
        message = QLabel(
            "Esta é uma senha temporária. Para continuar, defina sua nova senha."
        )
        message.setWordWrap(True)
        layout.addWidget(message)
        form = QFormLayout()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirmation = QLineEdit()
        self.confirmation.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Nova senha", self.password)
        form.addRow("Confirmar nova senha", self.confirmation)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar e continuar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        if self.password.text() != self.confirmation.text():
            QMessageBox.warning(self, "Nova senha", "As senhas informadas não coincidem.")
            return
        try:
            validate_password(self.password.text())
            completion = self.client.complete_password_change(self.password.text())
        except RuntimeError as error:
            QMessageBox.warning(self, "Nova senha", str(error))
            return
        except ValueError as error:
            QMessageBox.warning(self, "Nova senha", str(error))
            return
        self.user = completion.user
        PersonalRecoveryKeyDialog(completion.personal_recovery_key, self).exec()
        self.accept()


class PersonalRecoveryKeyDialog(QDialog):
    def __init__(
        self, recovery_key: str, parent=None, *, message: str | None = None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Chave pessoal de recuperação")
        self.setModal(True)
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        message_label = QLabel(
            message
            or "Guarde esta chave em um local seguro. Ela será exibida somente agora."
        )
        message_label.setWordWrap(True)
        layout.addWidget(message_label)
        self.key = QLineEdit(recovery_key)
        self.key.setReadOnly(True)
        layout.addWidget(self.key)
        copy_button = QPushButton("Copiar chave")
        copy_button.clicked.connect(self._copy)
        layout.addWidget(copy_button)
        conclude = QPushButton("Concluir")
        conclude.clicked.connect(self.accept)
        layout.addWidget(conclude)

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(self.key.text())


class PersonalRecoveryDialog(QDialog):
    def __init__(self, client: APIClient, identifier: str = "", parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.setWindowTitle("Finance — Recuperar senha")
        self.setModal(True)
        self.setFixedWidth(500)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title = QLabel("Recuperar senha")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        layout.addSpacing(16)

        intro = QLabel(
            "Informe o usuário ou e-mail, a chave de recuperação e defina uma nova senha. "
            "A chave será invalidada após o uso."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setSpacing(12)
        self.identifier = QLineEdit(identifier)
        self.identifier.setPlaceholderText("Usuário ou e-mail")
        self.recovery_key = QLineEdit()
        self.recovery_key.setPlaceholderText("XXXX-XXXX-XXXX-XXXX-XXXX-XXXX")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirmation = QLineEdit()
        self.confirmation.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setEnabled(False)
        self.confirmation.setEnabled(False)

        form.addRow("Usuário ou e-mail", self.identifier)
        form.addRow("Chave", self.recovery_key)
        form.addRow("Nova senha", self.password)
        form.addRow("Confirmar", self.confirmation)
        layout.addLayout(form)

        self.recovery_key.textChanged.connect(self._update_password_state)
        self.identifier.textChanged.connect(self._update_password_state)

        self.reset_button = QPushButton("Redefinir senha")
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self._reset)
        layout.addWidget(self.reset_button)

        self.assisted_button = QPushButton("Não tenho a chave — Recuperação assistida")
        self.assisted_button.clicked.connect(self._open_assisted_recovery)
        layout.addWidget(self.assisted_button)

        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)

    def _update_password_state(self) -> None:
        identifier_ok = bool(self.identifier.text().strip())
        key = self.recovery_key.text().strip()
        key_ok = len(key) >= 11
        enabled = identifier_ok and key_ok
        self.password.setEnabled(enabled)
        self.confirmation.setEnabled(enabled)
        self.reset_button.setEnabled(enabled)

    def _friendly_error(self, error: Exception) -> str:
        message = str(error)
        lowered = message.casefold()
        if 'string_too_short' in lowered or 'recovery_key' in lowered:
            return "Informe uma chave de recuperação válida."
        return message

    def _reset(self) -> None:
        if not self.password.isEnabled():
            QMessageBox.information(self, "Recuperar senha", "Informe uma chave de recuperação válida.")
            return
        if self.password.text() != self.confirmation.text():
            QMessageBox.warning(self, "Recuperar senha", "As senhas informadas não coincidem.")
            return
        try:
            validate_password(self.password.text())
            self.client.complete_personal_recovery(
                self.identifier.text().strip(),
                self.recovery_key.text().strip(),
                self.password.text(),
            )
        except (RuntimeError, ValueError) as error:
            QMessageBox.warning(self, "Recuperar senha", self._friendly_error(error))
            return
        QMessageBox.information(self, "Recuperar senha", "Senha redefinida com sucesso.")
        self.accept()

    def _open_assisted_recovery(self) -> None:
        AssistedRecoveryDialog(self.client, self.identifier.text().strip(), self).exec()


class AssistedRecoveryDialog(QDialog):
    SUPPORT_WHATSAPP = "(62) 9 8167-2265"

    def __init__(self, client: APIClient, identifier: str = "", parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.authorization_valid = False
        self.setWindowTitle("Finance — Recuperação assistida")
        self.setModal(True)
        self.setFixedWidth(620)
        self.resize(620, 640)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        title = QLabel("Recuperação assistida")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        intro = QLabel(
            "Fluxo: 1) gerar solicitação, 2) enviar ao suporte, 3) validar autorização, "
            "4) somente então definir a nova senha."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        request_group = QGroupBox("1. Solicitação")
        request_layout = QVBoxLayout(request_group)
        request_layout.setSpacing(8)

        email_form = QFormLayout()
        self.identifier = QLineEdit(identifier)
        self.identifier.setPlaceholderText("Usuário ou e-mail")
        email_form.addRow("Usuário ou e-mail", self.identifier)
        request_layout.addLayout(email_form)

        self.generate_button = QPushButton("Gerar código de solicitação")
        self.generate_button.clicked.connect(self._generate_request)
        request_layout.addWidget(self.generate_button)

        self.request_code = QPlainTextEdit()
        self.request_code.setReadOnly(True)
        self.request_code.setPlaceholderText("O código de solicitação aparecerá aqui.")
        self.request_code.setFixedHeight(72)
        request_layout.addWidget(self.request_code)

        self.copy_button = QPushButton("Copiar código")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self._copy_request)
        request_layout.addWidget(self.copy_button)

        helper = QLabel(
            f"Após gerar o código, clique em Copiar código e envie-o pelo WhatsApp para "
            f"{self.SUPPORT_WHATSAPP}. Você receberá uma autorização temporária para continuar."
        )
        helper.setWordWrap(True)
        request_layout.addWidget(helper)
        layout.addWidget(request_group)

        auth_group = QGroupBox("2. Validação da autorização")
        auth_layout = QVBoxLayout(auth_group)
        auth_layout.setSpacing(8)

        self.authorization = QPlainTextEdit()
        self.authorization.setPlaceholderText("Cole aqui a autorização temporária fornecida pelo suporte.")
        self.authorization.setFixedHeight(72)
        self.authorization.textChanged.connect(self._invalidate_authorization)
        auth_layout.addWidget(self.authorization)

        self.validate_button = QPushButton("Validar autorização")
        self.validate_button.setEnabled(False)
        self.validate_button.clicked.connect(self._validate_authorization)
        auth_layout.addWidget(self.validate_button)

        self.authorization_status = QLabel("Status: aguardando autorização temporária.")
        self.authorization_status.setWordWrap(True)
        auth_layout.addWidget(self.authorization_status)
        layout.addWidget(auth_group)

        pwd_group = QGroupBox("3. Nova senha")
        pwd_layout = QFormLayout(pwd_group)
        pwd_layout.setSpacing(8)

        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setEnabled(False)
        self.confirmation = QLineEdit()
        self.confirmation.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirmation.setEnabled(False)
        pwd_layout.addRow("Nova senha", self.password)
        pwd_layout.addRow("Confirmar", self.confirmation)
        layout.addWidget(pwd_group)

        self.reset_button = QPushButton("Redefinir senha")
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self._reset_password)
        layout.addWidget(self.reset_button)

        cancel = QPushButton("Cancelar")
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)

        self.authorization.textChanged.connect(
            lambda: self.validate_button.setEnabled(bool(self.authorization.toPlainText().strip()))
        )

    def _generate_request(self) -> None:
        identifier = self.identifier.text().strip()
        if not identifier:
            QMessageBox.information(self, "Recuperação assistida", "Informe seu usuário ou e-mail.")
            return
        self.request_code.clear()
        self.copy_button.setEnabled(False)
        self.authorization.clear()
        self.authorization_valid = False
        self.password.clear()
        self.confirmation.clear()
        self.password.setEnabled(False)
        self.confirmation.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.authorization_status.setText("Status: aguardando autorização temporária.")
        try:
            result = self.client.create_assisted_recovery_request(identifier)
        except RuntimeError as error:
            QMessageBox.warning(self, "Recuperação assistida", str(error))
            return
        code = str(result.get("request_code") or "").strip()
        if not code:
            QMessageBox.warning(self, "Recuperação assistida", "Usuário ou e-mail não localizado ou inativo.")
            return
        self.request_code.setPlainText(code)
        self.copy_button.setEnabled(True)

    def _copy_request(self) -> None:
        value = self.request_code.toPlainText().strip()
        if value:
            QGuiApplication.clipboard().setText(value)
            self.authorization_status.setText(
                f"Status: código copiado. Envie pelo WhatsApp para {self.SUPPORT_WHATSAPP}."
            )

    def _invalidate_authorization(self) -> None:
        self.authorization_valid = False
        self.password.setEnabled(False)
        self.confirmation.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.authorization_status.setText(
            "Status: autorização ainda não validada." if self.authorization.toPlainText().strip()
            else "Status: aguardando autorização temporária."
        )

    def _validate_authorization(self) -> None:
        value = self.authorization.toPlainText().strip()
        if not value:
            QMessageBox.information(self, "Recuperação assistida", "Informe o código de autorização.")
            return
        try:
            self.client.validate_assisted_recovery(value)
        except RuntimeError as error:
            self.authorization_status.setText("Status: autorização inválida.")
            QMessageBox.warning(self, "Recuperação assistida", str(error))
            return
        self.authorization_valid = True
        self.password.setEnabled(True)
        self.confirmation.setEnabled(True)
        self.reset_button.setEnabled(True)
        self.authorization_status.setText("Status: autorização válida. Defina sua nova senha.")
        self.password.setFocus()

    def _reset_password(self) -> None:
        if not self.authorization_valid:
            return
        if self.password.text() != self.confirmation.text():
            QMessageBox.warning(self, "Recuperação assistida", "As senhas informadas não coincidem.")
            return
        try:
            validate_password(self.password.text())
            self.client.complete_assisted_recovery(self.authorization.toPlainText().strip(), self.password.text())
        except (RuntimeError, ValueError) as error:
            QMessageBox.warning(self, "Recuperação assistida", str(error))
            return
        QMessageBox.information(self, "Recuperação assistida", "Senha redefinida com sucesso.")
        self.accept()


class LoginDialog(QDialog):
    def __init__(self, client: APIClient, parent=None) -> None:
        super().__init__(parent)
        self.client = client
        self.user: AuthenticatedUser | None = None
        self.setWindowTitle("Finance — Entrar")
        self.setModal(True)
        self.setFixedSize(500, 300)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 18, 28, 16)
        layout.setSpacing(0)

        title = QLabel("Finance")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: 700; color: #0B4A7F;")
        layout.addWidget(title)

        subtitle = QLabel("Entre com seu usuário e senha.")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #4A5568; font-size: 14px;")
        layout.addWidget(subtitle)
        layout.addSpacing(16)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)
        self.identifier = QLineEdit()
        self.identifier.setPlaceholderText("Usuário ou e-mail")
        self.identifier.setFixedHeight(36)
        self.password = QLineEdit()
        self.password.setPlaceholderText("Senha")
        self.password.setFixedHeight(36)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Usuário:", self.identifier)
        form.addRow("Senha:", self.password)
        layout.addLayout(form)
        layout.addSpacing(28)

        actions = QHBoxLayout()
        self.forgot_button = QPushButton("Esqueci minha senha")
        self.forgot_button.setFlat(True)
        self.forgot_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.forgot_button.setStyleSheet(
            "QPushButton { background: transparent; border: none; color: #0B4A7F; padding: 8px 0; text-align: left; }"
            "QPushButton:hover { color: #1D4ED8; text-decoration: underline; }"
            "QPushButton:focus { border: none; }"
        )
        self.forgot_button.clicked.connect(self._forgot)
        self.forgot_button.setFixedWidth(150)
        actions.addWidget(self.forgot_button)
        actions.addStretch()

        cancel = QPushButton("Cancelar")
        cancel.setFixedSize(120, 38)
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        actions.addSpacing(12)

        self.enter_button = QPushButton("Entrar")
        self.enter_button.setObjectName("primaryButton")
        self.enter_button.setProperty("buttonRole", "primary")
        self.enter_button.setFixedSize(120, 38)
        self.enter_button.clicked.connect(self._login)
        actions.addWidget(self.enter_button)
        layout.addLayout(actions)
        layout.addSpacing(8)

        support = QLabel("Precisa de ajuda? Suporte pelo WhatsApp:  (62) 9 8167-2265")
        support.setAlignment(Qt.AlignmentFlag.AlignCenter)
        support.setStyleSheet("color: #64748B; font-size: 11px;")
        layout.addWidget(support)

        self.password.returnPressed.connect(self._login)

    def _login(self) -> None:
        self.enter_button.setEnabled(False)
        try:
            self.user = self.client.login(self.identifier.text().strip(), self.password.text())
        except RuntimeError as error:
            QMessageBox.warning(self, "Acesso não autorizado", str(error))
        else:
            if self.user.must_change_password:
                change = RequiredPasswordChangeDialog(self.client, self)
                if change.exec() != QDialog.DialogCode.Accepted or change.user is None:
                    self.client.logout()
                    self.user = None
                    self.password.clear()
                    self.password.setFocus()
                    return
                self.user = change.user
            elif self.user.personal_recovery_key:
                PersonalRecoveryKeyDialog(self.user.personal_recovery_key, self).exec()
            self.accept()
        finally:
            self.enter_button.setEnabled(True)

    def _forgot(self) -> None:
        PersonalRecoveryDialog(self.client, self.identifier.text().strip(), self).exec()
