from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGridLayout, QHBoxLayout, QLabel,
    QDoubleSpinBox, QFrame, QLineEdit, QMessageBox, QPushButton, QSizePolicy, QSpinBox,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.services.administration_service import SystemInformation
from app.core.gui_rbac import ROLE_LABELS, role_label
from app.core.version import __version__
from finance_server.security import validate_password


USER_ROLES = (
    "ADMINISTRADOR", "GESTOR", "OPERADOR_FINANCEIRO", "OPERADOR_BOE", "CONSULTA",
)


class UserDialog(QDialog):
    def __init__(
        self, parent=None, *, user: dict | None = None,
        allow_administrator: bool = True,
    ) -> None:
        super().__init__(parent)
        self._editing = user is not None
        self.setWindowTitle("Editar usuário" if self._editing else "Novo usuário")
        layout = QFormLayout(self)
        self.name = QLineEdit(user.get("nome", "") if user else "")
        self.profile = QComboBox()
        roles = USER_ROLES if allow_administrator else USER_ROLES[1:]
        for role in roles:
            self.profile.addItem(ROLE_LABELS[role], role)
        if user:
            self.profile.setCurrentIndex(self.profile.findData(user["perfil"]))
        layout.addRow("Nome", self.name)
        if self._editing:
            self.active = QComboBox()
            self.active.addItem("Ativo", True)
            self.active.addItem("Inativo", False)
            self.active.setCurrentIndex(0 if user.get("ativo", True) else 1)
            layout.addRow("Perfil", self.profile)
            layout.addRow("Situação", self.active)
        else:
            self.email = QLineEdit()
            self.username = QLineEdit()
            self.password = QLineEdit()
            self.password.setEchoMode(QLineEdit.EchoMode.Password)
            self.password_confirmation = QLineEdit()
            self.password_confirmation.setEchoMode(QLineEdit.EchoMode.Password)
            layout.addRow("E-mail", self.email)
            layout.addRow("Usuário", self.username)
            layout.addRow("Perfil", self.profile)
            layout.addRow("Senha temporária", self.password)
            layout.addRow("Confirmar senha", self.password_confirmation)
            password_help = QLabel(
                "O usuário deverá criar uma nova senha no primeiro acesso."
            )
            password_help.setWordWrap(True)
            layout.addRow("", password_help)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def _validate(self) -> None:
        required = [self.name.text().strip()]
        if not self._editing:
            required.extend((self.email.text().strip(), self.username.text().strip(),
                             self.password.text(), self.password_confirmation.text()))
        if not all(required):
            QMessageBox.warning(self, "Dados obrigatórios", "Preencha todos os campos obrigatórios.")
            return
        if not self._editing and self.password.text() != self.password_confirmation.text():
            QMessageBox.warning(self, "Senha", "A senha e a confirmação devem ser iguais.")
            return
        if not self._editing:
            try:
                validate_password(self.password.text())
            except ValueError as error:
                QMessageBox.warning(self, "Senha", str(error))
                return
        self.accept()

    def payload(self) -> dict:
        if self._editing:
            return {
                "nome": self.name.text().strip(),
                "perfil": self.profile.currentData(),
                "ativo": self.active.currentData(),
            }
        return {
            "nome": self.name.text().strip(),
            "email": self.email.text().strip(),
            "username": self.username.text().strip(),
            "perfil": self.profile.currentData(),
            "password": self.password.text(),
        }


class RankingParametersWidget(QFrame):
    DECIMAL_FIELDS = (
        "minimum_achievement_percent",
        "billing_level_1_min", "billing_level_2_min", "billing_level_3_min",
        "acquisition_level_1_min", "acquisition_level_2_min", "acquisition_level_3_min",
        "first_place_award", "second_place_award", "third_place_award",
    )
    POINT_FIELDS = (
        "billing_level_1_points", "billing_level_2_points", "billing_level_3_points",
        "acquisition_level_1_points", "acquisition_level_2_points",
        "acquisition_level_3_points", "zero_cancellation_points",
        "positive_cancellation_points",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("rankingParametersCard")
        self.setStyleSheet(
            "QFrame#rankingParametersCard { background: #ffffff; border: 1px solid #d6dee8; "
            "border-radius: 6px; } QFrame#rankingParametersCard QLabel { border: none; "
            "background: transparent; }"
        )
        box = QVBoxLayout(self)
        box.setContentsMargins(10, 6, 10, 6)
        box.setSpacing(4)
        title = QLabel("PARÂMETROS DO RANKING")
        title.setObjectName("sectionTitle")
        box.addWidget(title)

        top = QHBoxLayout()
        top.addWidget(QLabel("Ano"))
        self.year = QSpinBox()
        self.year.setRange(2000, 9999)
        self.year.setValue(2026)
        self.year.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.year.installEventFilter(self)
        top.addWidget(self.year)
        top.addWidget(QLabel("Classificação mínima (%)"))
        self.fields: dict[str, QDoubleSpinBox | QSpinBox] = {}
        minimum = self._decimal_spin(4)
        self.fields["minimum_achievement_percent"] = minimum
        top.addWidget(minimum)
        self.load_button = QPushButton("Carregar")
        self.save_button = QPushButton("Salvar")
        top.addWidget(self.load_button)
        top.addWidget(self.save_button)
        self.status = QLabel("Selecione o ano e carregue a configuração.")
        top.addWidget(self.status, 1)
        box.addLayout(top)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(2)
        sections = ("FATURAMENTO", "CAPTAÇÃO", "CANCELAMENTO", "PREMIAÇÃO")
        for column, section in zip((0, 3, 6, 8), sections):
            grid.addWidget(QLabel(section), 0, column, 1, 2)

        for row, level in enumerate((1, 2, 3), 1):
            grid.addWidget(QLabel(f"Faixa {level} — mínimo / pontos"), row, 0)
            billing_min = self._decimal_spin(4)
            billing_points = self._points_spin()
            self.fields[f"billing_level_{level}_min"] = billing_min
            self.fields[f"billing_level_{level}_points"] = billing_points
            pair = self._pair(billing_min, billing_points)
            grid.addWidget(pair, row, 1)

            grid.addWidget(QLabel(f"Faixa {level} — mínimo / pontos"), row, 3)
            acquisition_min = self._decimal_spin(4)
            acquisition_points = self._points_spin()
            self.fields[f"acquisition_level_{level}_min"] = acquisition_min
            self.fields[f"acquisition_level_{level}_points"] = acquisition_points
            grid.addWidget(self._pair(acquisition_min, acquisition_points), row, 4)

        cancellation_rows = (
            ("Zero cancelamentos", "zero_cancellation_points"),
            ("Com cancelamento", "positive_cancellation_points"),
        )
        for row, (label, name) in enumerate(cancellation_rows, 1):
            grid.addWidget(QLabel(label), row, 6)
            field = self._points_spin()
            self.fields[name] = field
            grid.addWidget(field, row, 7)

        for row, (label, name) in enumerate((
            ("1º lugar", "first_place_award"),
            ("2º lugar", "second_place_award"),
            ("3º lugar", "third_place_award"),
        ), 1):
            grid.addWidget(QLabel(label), row, 8)
            field = self._decimal_spin(2)
            self.fields[name] = field
            grid.addWidget(field, row, 9)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(4, 1)
        grid.setColumnStretch(9, 1)
        box.addLayout(grid)

    def eventFilter(self, watched, event):
        if (
            isinstance(watched, (QSpinBox, QDoubleSpinBox))
            and event.type() == QEvent.Type.Wheel
            and not watched.hasFocus()
        ):
            event.ignore()
            return True
        return super().eventFilter(watched, event)

    def _decimal_spin(self, decimals: int) -> QDoubleSpinBox:
        field = QDoubleSpinBox()
        field.setDecimals(decimals)
        field.setRange(0, 999999999)
        field.setGroupSeparatorShown(True)
        field.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        field.installEventFilter(self)
        return field

    def _points_spin(self) -> QSpinBox:
        field = QSpinBox()
        field.setRange(0, 999999)
        field.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        field.installEventFilter(self)
        return field

    @staticmethod
    def _pair(first: QWidget, second: QWidget) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(first)
        layout.addWidget(second)
        return widget

    def show_parameters(self, values: dict | None) -> None:
        if values is None:
            for field in self.fields.values():
                field.setValue(0)
            self.status.setText(f"Nova configuração para {self.year.value()}.")
            return
        self.year.setValue(int(values["year"]))
        for name, field in self.fields.items():
            value = int(values[name]) if isinstance(field, QSpinBox) else float(values[name])
            field.setValue(value)
        self.set_status(f"Configuração de {self.year.value()} carregada.")

    def set_status(self, message: str, *, error: bool = False) -> None:
        self.status.setText(message)
        self.status.setStyleSheet("color: #b91c1c;" if error else "color: #166534;")

    def payload(self) -> dict:
        billing = [self.fields[f"billing_level_{level}_min"].value() for level in (1, 2, 3)]
        acquisition = [
            self.fields[f"acquisition_level_{level}_min"].value() for level in (1, 2, 3)
        ]
        if not billing[0] < billing[1] < billing[2]:
            raise ValueError("As faixas de faturamento devem estar em ordem crescente.")
        if not acquisition[0] < acquisition[1] < acquisition[2]:
            raise ValueError("As faixas de captação devem estar em ordem crescente.")
        return {
            name: (
                str(field.value()) if name in self.DECIMAL_FIELDS else int(field.value())
            )
            for name, field in self.fields.items()
        }


class AdministracaoPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)

        content = QWidget()
        content.setObjectName("contentPage")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(10, 2, 10, 8)
        layout.setSpacing(2)
        self._root_layout = layout

        self.scroll.setWidget(content)
        outer.addWidget(self.scroll)

        self.personal_widget = QWidget()
        self.personal_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        personal_layout = QVBoxLayout(self.personal_widget)
        personal_layout.setContentsMargins(0, 0, 0, 0)
        personal_layout.setSpacing(4)
        self._personal_layout = personal_layout
        self.page_title = QLabel("Administração")
        self.page_title.setObjectName("pageTitle")
        self.page_title.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        personal_layout.addWidget(self.page_title)

        self.page_description = QLabel("Gerencie as configurações do sistema e da sua conta.")
        self.page_description.setStyleSheet("font-size: 11px; color: #6B7280;")
        self.page_description.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        personal_layout.addWidget(self.page_description)

        self.account_widget = QFrame()
        self.account_widget.setObjectName("accountCard")
        self.account_widget.setFixedWidth(390)
        self.account_widget.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        self.account_widget.setStyleSheet("QFrame#accountCard { background: #ffffff; border: 1px solid #d6dee8; border-radius: 10px; }QFrame#accountCard QLabel { border: none; background: transparent; }")
        account_layout = QVBoxLayout(self.account_widget)
        account_layout.setContentsMargins(30, 26, 30, 26)
        account_layout.setSpacing(12)

        self.account_title = QLabel("Minha conta")
        self.account_title.setObjectName("sectionTitle")
        self.account_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        account_layout.addWidget(self.account_title)

        self.account_description = QLabel("Gerencie as configurações de segurança da sua conta.")
        self.account_description.setWordWrap(True)
        self.account_description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.account_description.setStyleSheet("color: #4A5568; border: none; background: transparent;")
        account_layout.addWidget(self.account_description)

        self.change_password_button = QPushButton("Alterar senha")
        self.change_password_button.setMinimumWidth(210)
        self.change_password_button.setMinimumHeight(40)
        account_actions = QHBoxLayout()
        account_actions.setContentsMargins(0, 6, 0, 0)
        account_actions.addStretch()
        account_actions.addWidget(self.change_password_button)
        account_actions.addStretch()
        account_layout.addLayout(account_actions)

        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("color: #E5E7EB;")
        account_layout.addWidget(separator)

        self.account_hint = QLabel("Mantenha sua conta segura.\nUtilize uma senha forte e pessoal.")
        self.account_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.account_hint.setStyleSheet("color: #6B7280; border: none; background: transparent;")
        account_layout.addWidget(self.account_hint)

        personal_layout.addWidget(
            self.account_widget,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
        layout.addWidget(self.personal_widget)
        layout.addSpacing(4)

        self.compact_account_widget = QFrame()
        self.compact_account_widget.setObjectName("accountCard")
        self.compact_account_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.compact_account_widget.setStyleSheet(
            "QFrame#accountCard { background: #ffffff; border: 1px solid #d6dee8; "
            "border-radius: 10px; } "
            "QFrame#accountCard QLabel { border: none; background: transparent; }"
        )
        compact_layout = QHBoxLayout(self.compact_account_widget)
        compact_layout.setContentsMargins(12, 5, 12, 5)
        compact_layout.setSpacing(8)
        compact_text = QVBoxLayout()
        compact_text.setSpacing(0)
        compact_title = QLabel("Minha conta")
        compact_title.setObjectName("sectionTitle")
        compact_description = QLabel(
            "Gerencie as configurações de segurança da sua conta."
        )
        compact_description.setStyleSheet(
            "color: #4A5568; border: none; background: transparent;"
        )
        compact_text.addWidget(compact_title)
        compact_text.addWidget(compact_description)
        compact_layout.addLayout(compact_text, 1)
        self.compact_change_password_button = QPushButton("Alterar senha")
        compact_layout.addWidget(self.compact_change_password_button)
        layout.addWidget(self.compact_account_widget)

        self.info_widget = QFrame()
        self.info_widget.setObjectName("infoCompact")
        self.info_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.info_widget.setStyleSheet("QFrame#infoCompact { background: #ffffff; border: 1px solid #d6dee8; border-radius: 6px; }QFrame#infoCompact QLabel { border: none; background: transparent; }")
        info_box = QVBoxLayout(self.info_widget)
        info_box.setContentsMargins(10, 6, 10, 6)
        info_box.setSpacing(3)
        info_title = QLabel("Informações do sistema")
        info_title.setObjectName("sectionTitle")
        info_box.addWidget(info_title)
        info_grid_widget = QWidget()
        info_grid = QGridLayout(info_grid_widget)
        info_grid.setContentsMargins(0, 0, 0, 0)
        info_grid.setHorizontalSpacing(10)
        info_grid.setVerticalSpacing(0)
        self.fields = {key: QLabel("—") for key in ("application", "environment", "version", "database", "revision", "logs", "entities", "entries", "boe", "targets")}
        left_fields = (("Aplicação", "application"), ("Ambiente", "environment"), ("Versão", "version"), ("Banco utilizado", "database"), ("Revisão Alembic", "revision"))
        right_fields = (("Diretório de logs", "logs"), ("Entidades", "entities"), ("Lançamentos", "entries"), ("Imports BOE", "boe"), ("Metas", "targets"))
        for row, ((ll, lk), (rl, rk)) in enumerate(zip(left_fields, right_fields)):
            llw = QLabel(ll)
            rlw = QLabel(rl)
            for widget in (llw, self.fields[lk], rlw, self.fields[rk]):
                widget.setStyleSheet("")
            self.fields[lk].setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.fields[rk].setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            info_grid.addWidget(llw, row, 0)
            info_grid.addWidget(self.fields[lk], row, 1)
            info_grid.addWidget(rlw, row, 2)
            info_grid.addWidget(self.fields[rk], row, 3)
        info_grid.setColumnStretch(1, 1)
        info_grid.setColumnStretch(3, 1)
        info_grid_widget.setFixedHeight(info_grid_widget.sizeHint().height())
        info_box.addWidget(info_grid_widget)
        controls_widget = QWidget()
        controls = QHBoxLayout(controls_widget)
        controls.setContentsMargins(0, 1, 0, 0)
        controls.setSpacing(6)
        self.refresh_button = QPushButton("Consultar informações")
        self.check_updates_button = QPushButton("Verificar atualizações")
        self.logs_button = QPushButton("Abrir diretório de logs")
        self.backup_button = QPushButton("Fazer Backup")
        self.import_button = QPushButton("Importação histórica")
        self.server_button = QPushButton("Status do servidor")
        self.users_button = QPushButton("Usuários")
        self.audit_button = QPushButton("Auditoria")
        for button in (
            self.refresh_button,
            self.check_updates_button,
            self.logs_button,
            self.backup_button,
            self.import_button,
            self.server_button,
        ):
            button.setMinimumHeight(28)
            controls.addWidget(button)
        controls.addStretch()
        info_box.addWidget(controls_widget)
        self.info_widget.setMinimumHeight(self.info_widget.sizeHint().height())
        layout.addWidget(self.info_widget, 0)

        self.ranking_parameters_widget = RankingParametersWidget()
        layout.addWidget(self.ranking_parameters_widget, 0)

        self.exports_title = QLabel("Histórico de exportações CSV")
        layout.addWidget(self.exports_title)
        self.exports = QTableWidget(0, 3)
        self.exports.setHorizontalHeaderLabels(["Data", "Ano", "Diretório"])
        self.exports.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.exports.setMinimumHeight(104)
        self.exports.setMaximumHeight(112)
        layout.addWidget(self.exports)
        self.user_actions_widget = QWidget()
        user_actions = QHBoxLayout(self.user_actions_widget)
        user_actions.setContentsMargins(0, 0, 0, 0)
        user_actions.setSpacing(6)
        user_actions.addWidget(self.audit_button)
        user_actions.addWidget(self.users_button)
        self.new_user_button = QPushButton("Novo usuário")
        self.edit_user_button = QPushButton("Editar")
        self.toggle_user_button = QPushButton("Ativar/Inativar")
        self.reset_password_button = QPushButton("Redefinir senha")
        self.reload_users_button = QPushButton("Atualizar lista")
        for button in (self.new_user_button, self.edit_user_button,
                       self.toggle_user_button, self.reset_password_button,
                       self.reload_users_button):
            user_actions.addWidget(button)
        user_actions.addStretch()
        layout.addWidget(self.user_actions_widget)
        self.content_title = QLabel("Usuários")
        self.content_title.setObjectName("sectionTitle")
        layout.addWidget(self.content_title)
        self.multiuser_table = QTableWidget(0, 5)
        self.multiuser_table.setHorizontalHeaderLabels(
            ["Nome", "E-mail", "Usuário", "Perfil", "Situação"]
        )
        self.multiuser_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.multiuser_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.multiuser_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.multiuser_table.setMinimumHeight(180)
        self.multiuser_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        layout.addWidget(self.multiuser_table, 1)
        self.status = QLabel()
        layout.addWidget(self.status)

        self._can_read_admin = True
        self._can_manage_users = True

        self._administrative_widgets = (
            self.info_widget,
            self.ranking_parameters_widget,
            self.refresh_button,
            self.check_updates_button,
            self.logs_button,
            self.backup_button,
            self.import_button,
            self.exports_title,
            self.exports,
            self.server_button,
            self.users_button,
            self.audit_button,
            self.user_actions_widget,
            self.content_title,
            self.multiuser_table,
        )

    def set_user_management_enabled(self, enabled: bool) -> None:
        for button in (self.users_button, self.new_user_button, self.edit_user_button,
                       self.toggle_user_button, self.reset_password_button,
                       self.reload_users_button):
            button.setEnabled(enabled)

    def set_remote_action_permissions(
        self, *, can_read_admin: bool, can_manage_users: bool, can_read_audit: bool,
        can_manage_ranking: bool = False,
    ) -> None:
        self._can_read_admin = can_read_admin
        self._can_manage_users = can_manage_users
        for widget in self._administrative_widgets:
            widget.setVisible(can_read_admin)
        self.set_user_management_enabled(can_manage_users)
        self.audit_button.setEnabled(can_read_audit)
        self.ranking_parameters_widget.setVisible(can_manage_ranking)

        # Quando o usuário possui apenas a área pessoal, centraliza todo o conteúdo
        # relevante da página e oculta mensagens operacionais administrativas.
        personal_only = not can_read_admin
        text_alignment = (
            Qt.AlignmentFlag.AlignCenter
            if personal_only
            else Qt.AlignmentFlag.AlignLeft
        )
        self.page_title.setAlignment(text_alignment)
        self.page_description.setAlignment(text_alignment)
        self.status.setVisible(can_read_admin)
        self.account_widget.setVisible(personal_only)
        self.compact_account_widget.setVisible(can_read_admin)
        self.user_actions_widget.setVisible(can_read_admin and can_manage_users)

        if personal_only:
            self._root_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._personal_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self._root_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self._personal_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
            self.status.setAlignment(Qt.AlignmentFlag.AlignLeft)

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
            "environment": health.get("environment", unavailable),
            "version": __version__,
            "database": health.get("database", unavailable),
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

    def set_update_check_running(self, running: bool) -> None:
        self.check_updates_button.setEnabled(not running)
        self.check_updates_button.setText(
            "Consultando..." if running else "Verificar atualizações"
        )

    def show_remote_rows(self, rows: list[tuple[str, str, str, str]]) -> None:
        self.content_title.setText("Auditoria")
        self.user_actions_widget.setVisible(self._can_read_admin)
        for button in (
            self.new_user_button,
            self.edit_user_button,
            self.toggle_user_button,
            self.reset_password_button,
            self.reload_users_button,
        ):
            button.setVisible(True)
            button.setEnabled(False)
        self.multiuser_table.setColumnCount(4)
        self.multiuser_table.setHorizontalHeaderLabels(
            ["ID/Data", "Nome/Usuário", "Perfil/Ação", "Estado/Módulo"]
        )
        self.multiuser_table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                self.multiuser_table.setItem(row, column, QTableWidgetItem(value))
        self.multiuser_table.resizeColumnsToContents()

    def show_users(self, users: list[dict]) -> None:
        self.content_title.setText("Usuários")
        self.user_actions_widget.setVisible(self._can_read_admin)
        for button in (
            self.new_user_button,
            self.edit_user_button,
            self.toggle_user_button,
            self.reset_password_button,
            self.reload_users_button,
        ):
            button.setVisible(True)
            button.setEnabled(self._can_manage_users)
        self.multiuser_table.setColumnCount(5)
        self.multiuser_table.setHorizontalHeaderLabels(
            ["Nome", "E-mail", "Usuário", "Perfil", "Situação"]
        )
        self.multiuser_table.setRowCount(len(users))
        for row, user in enumerate(users):
            values = (user["nome"], user["email"], user["username"],
                      role_label(user["perfil"]),
                      "Ativo" if user["ativo"] else "Inativo")
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, user if column == 0 else None)
                self.multiuser_table.setItem(row, column, item)
        self.multiuser_table.resizeColumnsToContents()

    def selected_user(self) -> dict | None:
        row = self.multiuser_table.currentRow()
        if row < 0 or self.multiuser_table.columnCount() != 5:
            return None
        item = self.multiuser_table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None
