from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QMessageBox

from app.gui.pages.administracao import AdministracaoPage, UserDialog
from app.api_client.client import AuthenticatedUser


def _user(*, active=True):
    return {
        "id": 7,
        "nome": "Usuário Teste",
        "email": "usuario@finance.test",
        "username": "usuario.teste",
        "perfil": "GESTOR",
        "ativo": active,
    }


def test_user_table_has_business_columns_and_never_displays_password(qtbot):
    page = AdministracaoPage()
    qtbot.addWidget(page)
    user = {**_user(), "password": "NeverDisplayThis", "password_hash": "NeverDisplayHash"}

    page.show_users([user])

    headers = [page.multiuser_table.horizontalHeaderItem(index).text() for index in range(5)]
    visible = " ".join(
        page.multiuser_table.item(0, column).text() for column in range(5)
    )
    assert headers == ["Nome", "E-mail", "Usuário", "Perfil", "Situação"]
    assert "ID" not in headers
    assert "NeverDisplayThis" not in visible
    assert "NeverDisplayHash" not in visible
    page.multiuser_table.selectRow(0)
    assert page.selected_user()["id"] == 7


def test_profile_labels_are_friendly_while_payload_keeps_internal_values(qtbot):
    expected = [
        "Administrador", "Gestor", "Operador financeiro", "Operador BOE", "Consulta",
    ]
    dialog = UserDialog()
    qtbot.addWidget(dialog)

    assert [dialog.profile.itemText(index) for index in range(5)] == expected
    assert [dialog.profile.itemData(index) for index in range(5)] == [
        "ADMINISTRADOR", "GESTOR", "OPERADOR_FINANCEIRO", "OPERADOR_BOE", "CONSULTA",
    ]
    dialog.profile.setCurrentIndex(2)
    assert dialog.payload()["perfil"] == "OPERADOR_FINANCEIRO"


def test_new_user_dialog_validates_password_confirmation(qtbot, monkeypatch):
    dialog = UserDialog()
    qtbot.addWidget(dialog)
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[2]))
    dialog.name.setText("Usuário Teste")
    dialog.email.setText("usuario@finance.test")
    dialog.username.setText("usuario.teste")
    dialog.password.setText("Strong!Pass123")
    dialog.password_confirmation.setText("Different!Pass123")

    dialog._validate()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert messages == ["A senha e a confirmação devem ser iguais."]


def test_new_user_dialog_uses_central_password_policy(qtbot, monkeypatch):
    dialog = UserDialog()
    qtbot.addWidget(dialog)
    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[2]))
    dialog.name.setText("Usuário Teste")
    dialog.email.setText("usuario@finance.test")
    dialog.username.setText("usuario.teste")
    dialog.password.setText("abcdef")
    dialog.password_confirmation.setText("abcdef")

    dialog._validate()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert messages == [
        "A senha deve possuir no mínimo 6 caracteres, incluindo uma letra maiúscula, "
        "uma letra minúscula e um número."
    ]


def test_remote_user_create_edit_toggle_and_api_error(qtbot, monkeypatch, tmp_path):
    from app.core.config import Settings
    import app.gui.main_window as module
    from tests.test_sprint12a1_centralization import FakeRemoteAPI

    class API(FakeRemoteAPI):
        def __init__(self):
            super().__init__()
            self.users = [_user()]
            self.created = []
            self.updated = []

        def list_users(self):
            return [dict(value) for value in self.users]

        def create_user(self, payload):
            self.created.append(payload)
            created = {"id": 8, "ativo": True, **payload}
            created.pop("password")
            self.users.append(created)
            return created

        def update_user(self, user_id, payload):
            self.updated.append((user_id, payload))
            self.users[0].update(payload)
            return dict(self.users[0])

    class AcceptedDialog:
        payload_value = {}

        def __init__(self, parent=None, *, user=None, **_kwargs):
            self.user = user

        def exec(self):
            return QDialog.DialogCode.Accepted

        def payload(self):
            return dict(self.payload_value)

    api = API()
    settings = Settings("Finance", "development", False,
                        f"sqlite:///{(tmp_path / 'unused.db').as_posix()}", "INFO", tmp_path)
    window = module.MainWindow(settings, api_client=api)
    qtbot.addWidget(window)
    page = window.pages["administracao"]
    window._load_remote_users(page)

    AcceptedDialog.payload_value = {
        "nome": "Novo Usuário", "email": "novo@finance.test", "username": "novo",
        "perfil": "CONSULTA", "password": "Strong!Pass123",
    }
    monkeypatch.setattr(module, "UserDialog", AcceptedDialog)
    window._create_remote_user(page)
    assert api.created[-1]["password"] == "Strong!Pass123"
    assert page.status.text() == "Usuário criado com sucesso."

    page.multiuser_table.selectRow(0)
    AcceptedDialog.payload_value = {"nome": "Nome Editado", "perfil": "ADMINISTRADOR", "ativo": True}
    window._edit_remote_user(page)
    assert api.updated[-1] == (7, AcceptedDialog.payload_value)

    page.multiuser_table.selectRow(0)
    window._toggle_remote_user(page)
    assert api.updated[-1] == (7, {"ativo": False})
    assert page.status.text() == "Usuário inativado com sucesso."

    def fail(_payload):
        raise RuntimeError("Email ou username já cadastrado.")

    api.create_user = fail
    window._create_remote_user(page)
    assert "Email ou username já cadastrado" in page.status.text()
    assert "#b91c1c" in page.status.styleSheet()


def test_required_password_change_dialog_completes_with_shared_policy(qtbot, monkeypatch):
    from app.gui.login_dialog import RequiredPasswordChangeDialog

    class API:
        changed = []

        def complete_password_change(self, password):
            from app.api_client.client import PasswordChangeCompletion
            self.changed.append(password)
            return PasswordChangeCompletion(
                AuthenticatedUser(9, "Novo", "CONSULTA", False), "FIN-test-key"
            )

    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    monkeypatch.setattr(
        "app.gui.login_dialog.PersonalRecoveryKeyDialog.exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    dialog = RequiredPasswordChangeDialog(API())
    qtbot.addWidget(dialog)
    dialog.password.setText("Finance1")
    dialog.confirmation.setText("Finance1")

    dialog._save()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.user.must_change_password is False
    assert dialog.client.changed == ["Finance1"]


def test_cancelled_required_password_change_does_not_accept_login(qtbot, monkeypatch):
    import app.gui.login_dialog as module

    class API:
        logged_out = False

        def login(self, identifier, password):
            return AuthenticatedUser(9, "Novo", "CONSULTA", True)

        def logout(self):
            self.logged_out = True

    class CancelledDialog:
        user = None

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(module, "RequiredPasswordChangeDialog", CancelledDialog)
    api = API()
    dialog = module.LoginDialog(api)
    qtbot.addWidget(dialog)
    dialog.identifier.setText("novo")
    dialog.password.setText("Abc123")

    dialog._login()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.user is None
    assert api.logged_out is True


def test_api_client_change_password_sends_authenticated_contract(monkeypatch):
    from app.api_client.client import APIClient

    client = APIClient("http://finance.test")
    calls = []
    monkeypatch.setattr(
        client,
        "_request",
        lambda method, path, **kwargs: calls.append((method, path, kwargs)),
    )

    client.change_password("Atual1", "NovaSenha2")

    assert calls == [(
        "POST",
        "/api/v1/auth/change-password",
        {"json": {"current_password": "Atual1", "new_password": "NovaSenha2"}},
    )]
    client.close()


def test_voluntary_password_dialog_validates_and_handles_success(qtbot, monkeypatch):
    from app.gui.login_dialog import ChangePasswordDialog

    class API:
        calls = []

        def change_password(self, current_password, new_password):
            self.calls.append((current_password, new_password))

    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[2]))
    monkeypatch.setattr(QMessageBox, "information", lambda *args: messages.append(args[2]))
    dialog = ChangePasswordDialog(API())
    qtbot.addWidget(dialog)
    assert dialog.current_password.echoMode() == dialog.current_password.EchoMode.Password
    dialog.current_password.setText("Atual1")
    dialog.new_password.setText("Finance1")
    dialog.confirmation.setText("Finance1")

    dialog._save()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.client.calls == [("Atual1", "Finance1")]
    assert messages == ["Senha alterada com sucesso."]


def test_voluntary_password_dialog_rejects_confirmation_policy_and_api_error(
    qtbot, monkeypatch
):
    from app.gui.login_dialog import ChangePasswordDialog

    class API:
        def change_password(self, current_password, new_password):
            raise RuntimeError("Senha atual inválida.")

    messages = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[2]))
    dialog = ChangePasswordDialog(API())
    qtbot.addWidget(dialog)
    dialog.current_password.setText("Atual1")

    dialog.new_password.setText("Finance1")
    dialog.confirmation.setText("Outra2")
    dialog._save()
    assert messages[-1] == "As senhas informadas não coincidem."

    dialog.new_password.setText("fraca")
    dialog.confirmation.setText("fraca")
    dialog._save()
    assert "no mínimo 6 caracteres" in messages[-1]

    dialog.new_password.setText("Finance1")
    dialog.confirmation.setText("Finance1")
    dialog._save()
    assert messages[-1] == "Senha atual inválida."
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_administration_actions_follow_specific_role_permissions(qtbot, tmp_path):
    from app.core.config import Settings
    from app.gui.main_window import MainWindow
    from tests.test_sprint12a1_centralization import FakeRemoteAPI

    settings = Settings(
        "Finance", "development", False,
        f"sqlite:///{(tmp_path / 'unused.db').as_posix()}", "INFO", tmp_path,
    )
    administrator = MainWindow(
        settings, api_client=FakeRemoteAPI(),
        authenticated_user=AuthenticatedUser(1, "Admin", "ADMINISTRADOR", False),
    )
    manager = MainWindow(
        settings, api_client=FakeRemoteAPI(),
        authenticated_user=AuthenticatedUser(2, "Gestor", "GESTOR", False),
    )
    qtbot.addWidget(administrator)
    qtbot.addWidget(manager)

    admin_page = administrator.pages["administracao"]
    assert admin_page.new_user_button.isEnabled()
    assert admin_page.audit_button.isEnabled()

    manager_page = manager.pages["administracao"]
    assert manager_page.users_button.isEnabled()
    assert manager_page.new_user_button.isEnabled()
    assert manager_page.edit_user_button.isEnabled()
    assert manager_page.toggle_user_button.isEnabled()
    assert manager_page.reset_password_button.isEnabled()
    assert not manager_page.audit_button.isEnabled()
    assert manager_page.refresh_button.isEnabled()
    assert not hasattr(manager.header, "change_password_button")
    assert not manager_page.change_password_button.isVisibleTo(manager_page)
    assert manager_page.compact_change_password_button.isVisibleTo(manager_page)


def test_non_administrative_user_sees_only_personal_administration_area(
    qtbot, tmp_path, monkeypatch
):
    from app.core.config import Settings
    import app.gui.main_window as module
    from tests.test_sprint12a1_centralization import FakeRemoteAPI

    class Dialog:
        calls = 0

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            self.__class__.calls += 1
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(module, "ChangePasswordDialog", Dialog)
    settings = Settings(
        "Finance", "development", False,
        f"sqlite:///{(tmp_path / 'unused.db').as_posix()}", "INFO", tmp_path,
    )
    window = module.MainWindow(
        settings, api_client=FakeRemoteAPI(),
        authenticated_user=AuthenticatedUser(3, "Consulta", "CONSULTA", False),
    )
    qtbot.addWidget(window)
    page = window.pages["administracao"]

    assert "administracao" in window.navigation.allowed_pages
    assert page.change_password_button.isVisibleTo(page)
    assert not page.info_widget.isVisibleTo(page)
    assert not page.new_user_button.isVisibleTo(page)
    assert not page.audit_button.isVisibleTo(page)
    page.change_password_button.click()
    assert Dialog.calls == 1


def test_administrative_layout_uses_compact_account_and_expanding_content_table(qtbot):
    from PySide6.QtWidgets import QSizePolicy

    page = AdministracaoPage()
    qtbot.addWidget(page)
    page.set_remote_action_permissions(
        can_read_admin=True, can_manage_users=True, can_read_audit=True
    )

    assert not page.account_widget.isVisibleTo(page)
    assert page.compact_account_widget.isVisibleTo(page)
    assert page.compact_account_widget.sizePolicy().verticalPolicy() == (
        QSizePolicy.Policy.Preferred
    )
    assert page.multiuser_table.minimumHeight() == 180
    assert page.multiuser_table.sizePolicy().verticalPolicy() == (
        QSizePolicy.Policy.Expanding
    )


def test_users_and_audit_modes_are_visually_distinct(qtbot):
    page = AdministracaoPage()
    qtbot.addWidget(page)
    page.set_remote_action_permissions(
        can_read_admin=True, can_manage_users=True, can_read_audit=True
    )

    page.show_users([_user()])
    assert page.content_title.text() == "Usuários"
    assert page.user_actions_widget.isVisibleTo(page)

    page.show_remote_rows([("10/09/2026", "admin", "LOGIN", "User")])
    assert page.content_title.text() == "Auditoria"
    assert page.user_actions_widget.isVisibleTo(page)
    assert all(not button.isEnabled() for button in (
        page.new_user_button,
        page.edit_user_button,
        page.toggle_user_button,
        page.reset_password_button,
        page.reload_users_button,
    ))

    page.show_users([_user()])
    assert page.content_title.text() == "Usuários"
    assert page.user_actions_widget.isVisibleTo(page)
    assert all(button.isEnabled() for button in (
        page.new_user_button,
        page.edit_user_button,
        page.toggle_user_button,
        page.reset_password_button,
        page.reload_users_button,
    ))


def test_manual_personal_key_regeneration_has_no_client_or_gui_action():
    from app.api_client.client import APIClient
    from app.gui.pages.administracao import AdministracaoPage
    from app.widgets.app_header import AppHeader

    assert not hasattr(APIClient, "regenerate_personal_recovery_key")
    assert not hasattr(AdministracaoPage(), "regenerate_recovery_key_button")
    assert not hasattr(AppHeader(), "regenerate_recovery_key_button")
