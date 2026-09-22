import pytest
from PySide6.QtWidgets import QLabel, QDialog, QStackedWidget

from app.api_client.client import AuthenticatedUser
from app.core.gui_rbac import (
    MODULE_PERMISSIONS, allowed_dashboard_areas, allowed_modules,
    allowed_registration_areas,
)
from app.gui.controllers.navigation_controller import NavigationController
from finance_server.models import UserRole
from finance_server.rbac import ROLE_PERMISSIONS


EXPECTED_MODULES = {
    "ADMINISTRADOR": {
        "dashboard", "financeiro", "orcamento", "boe", "metas",
        "cadastros", "relatorios", "administracao",
    },
    "GESTOR": {
        "dashboard", "financeiro", "orcamento", "boe", "metas",
        "cadastros", "relatorios", "administracao",
    },
    "OPERADOR_FINANCEIRO": {
        "dashboard", "financeiro", "orcamento", "cadastros",
        "administracao",
    },
    "OPERADOR_BOE": {
        "dashboard", "boe", "cadastros",
        "administracao",
    },
    "CONSULTA": {
        "dashboard", "financeiro", "orcamento", "boe", "metas",
        "relatorios", "administracao",
    },
}


@pytest.mark.parametrize("role, expected", EXPECTED_MODULES.items())
def test_visible_modules_are_derived_from_official_role_permissions(role, expected):
    assert allowed_modules(role) == expected
    official = ROLE_PERMISSIONS[UserRole(role)]
    expected_from_rbac = {
        module for module, permission in MODULE_PERMISSIONS.items()
        if "*" in official or permission in official
    }
    # Administração contém Minha conta para todo usuário autenticado.
    expected_from_rbac.add("administracao")
    # Cadastros é controlado por subáreas, não por uma única permissão de módulo.
    if allowed_registration_areas(role):
        expected_from_rbac.add("cadastros")
    assert expected == expected_from_rbac


def test_programmatic_navigation_to_forbidden_page_is_blocked(qtbot):
    stack = QStackedWidget()
    qtbot.addWidget(stack)
    indexes = {
        "dashboard": stack.addWidget(QLabel("Dashboard")),
        "administracao": stack.addWidget(QLabel("Administração")),
    }
    navigation = NavigationController(stack, indexes, {"dashboard"})
    navigation.navigate_to("dashboard")

    with pytest.raises(PermissionError, match="Acesso não autorizado"):
        navigation.navigate_to("administracao")

    assert stack.currentIndex() == indexes["dashboard"]


def test_first_page_is_always_an_authorized_page(qtbot):
    stack = QStackedWidget()
    qtbot.addWidget(stack)
    indexes = {
        "dashboard": stack.addWidget(QLabel("Dashboard")),
        "financeiro": stack.addWidget(QLabel("Financeiro")),
    }
    navigation = NavigationController(stack, indexes, {"financeiro"})
    assert navigation.first_allowed_page() == "financeiro"
    navigation.navigate_to(navigation.first_allowed_page())
    assert stack.currentIndex() == indexes["financeiro"]


def test_operator_dashboard_areas_are_strictly_segregated():
    assert allowed_dashboard_areas("OPERADOR_FINANCEIRO") == {"financial"}
    assert allowed_dashboard_areas("OPERADOR_BOE") == {"boe"}
    assert allowed_dashboard_areas("ADMINISTRADOR") == {
        "financial", "boe", "targets",
    }
    assert allowed_dashboard_areas("GESTOR") == {
        "financial", "boe", "targets",
    }


@pytest.mark.parametrize(
    "role,expected_path",
    [
        ("OPERADOR_FINANCEIRO", "/api/v1/dashboard/financial"),
        ("OPERADOR_BOE", "/api/v1/dashboard/boe"),
    ],
)
def test_operator_dashboard_service_requests_only_authorized_area(
    role, expected_path,
):
    from app.services.remote_services import RemoteDashboardService

    class API:
        def __init__(self):
            self.calls = []

        def get(self, path):
            self.calls.append(path)
            return {}

    api = API()
    RemoteDashboardService(api, allowed_dashboard_areas(role)).get_dashboard_data(
        2026, 9
    )

    assert len(api.calls) == 1
    assert api.calls[0].startswith(expected_path)


def test_sidebar_updates_after_logout_and_login_with_another_role(qtbot, monkeypatch, tmp_path):
    from app.core.config import Settings
    import app.gui.main_window as module
    from tests.test_sprint12a1_centralization import FakeRemoteAPI

    class Login:
        user = AuthenticatedUser(2, "Operador BOE", "OPERADOR_BOE", False)

        def __init__(self, *args, **kwargs):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(module, "LoginDialog", Login)
    settings = Settings(
        "Finance", "development", False,
        f"sqlite:///{(tmp_path / 'unused.db').as_posix()}", "INFO", tmp_path,
    )
    api = FakeRemoteAPI()
    window = module.MainWindow(
        settings, api_client=api,
        authenticated_user=AuthenticatedUser(1, "Administrador", "ADMINISTRADOR", False),
    )
    qtbot.addWidget(window)
    assert all(not button.isHidden() for button in window.sidebar.buttons.values())

    window._logout()

    visible = {key for key, button in window.sidebar.buttons.items() if not button.isHidden()}
    assert visible == EXPECTED_MODULES["OPERADOR_BOE"]
    assert window.navigation.first_allowed_page() == "dashboard"
    assert window.header.user.text() == "Operador BOE\nOperador BOE"


@pytest.mark.parametrize("role", EXPECTED_MODULES)
def test_main_window_sidebar_matches_role(qtbot, tmp_path, role):
    from app.core.config import Settings
    from app.gui.main_window import MainWindow
    from tests.test_sprint12a1_centralization import FakeRemoteAPI

    settings = Settings(
        "Finance", "development", False,
        f"sqlite:///{(tmp_path / f'{role}.db').as_posix()}", "INFO", tmp_path,
    )
    window = MainWindow(
        settings, api_client=FakeRemoteAPI(),
        authenticated_user=AuthenticatedUser(1, role, role, False),
    )
    qtbot.addWidget(window)
    visible = {key for key, button in window.sidebar.buttons.items() if not button.isHidden()}
    assert visible == EXPECTED_MODULES[role]
    assert window.navigation.first_allowed_page() in visible


@pytest.mark.parametrize(
    "role,expected_calls",
    [
        ("OPERADOR_FINANCEIRO", ["/api/v1/catalog"]),
        ("OPERADOR_BOE", ["/api/v1/entities"]),
    ],
)
def test_registration_loads_only_authorized_subarea(
    qtbot, role, expected_calls,
):
    from app.gui.controllers.registration_controller import RemoteRegistrationController
    from app.gui.pages.cadastros import CadastrosPage
    from app.core.gui_rbac import allowed_registration_areas

    class API:
        def __init__(self):
            self.calls = []

        def get(self, path):
            self.calls.append(path)
            return []

    page = CadastrosPage()
    qtbot.addWidget(page)
    api = API()
    RemoteRegistrationController(
        page, api, allowed_areas=allowed_registration_areas(role)
    )

    assert api.calls == expected_calls


def test_operator_actions_follow_final_matrix_and_personal_admin_remains(qtbot, tmp_path):
    from app.core.config import Settings
    from app.gui.main_window import MainWindow
    from tests.test_sprint12a1_centralization import FakeRemoteAPI

    settings = Settings(
        "Finance", "development", False,
        f"sqlite:///{(tmp_path / 'unused.db').as_posix()}", "INFO", tmp_path,
    )
    financial = MainWindow(
        settings, api_client=FakeRemoteAPI(),
        authenticated_user=AuthenticatedUser(
            1, "Financeiro", "OPERADOR_FINANCEIRO", False
        ),
    )
    boe = MainWindow(
        settings, api_client=FakeRemoteAPI(),
        authenticated_user=AuthenticatedUser(2, "BOE", "OPERADOR_BOE", False),
    )
    qtbot.addWidget(financial)
    qtbot.addWidget(boe)

    assert financial.pages["financeiro"].new_entry_button.isEnabled()
    assert not financial.pages["orcamento"].new_button.isEnabled()
    assert financial.pages["cadastros"].tabs.isTabVisible(1)
    assert not financial.pages["cadastros"].tabs.isTabVisible(0)
    assert financial.pages["cadastros"].new_catalog_button.isEnabled()
    assert financial.pages["cadastros"].edit_catalog_button.isEnabled()
    assert not boe.pages["boe"].import_button.isEnabled()
    assert boe.pages["cadastros"].tabs.isTabVisible(0)
    assert not boe.pages["cadastros"].tabs.isTabVisible(1)
    for window in (financial, boe):
        page = window.pages["administracao"]
        assert page.change_password_button.isVisibleTo(page)
        assert not page.new_user_button.isVisibleTo(page)
