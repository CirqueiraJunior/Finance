from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.core.branding import ASSETS_DIR, OFFICIAL_LOGO, OFFICIAL_SPLASH, official_icon
from app.core.config import get_settings
from app.gui.main_window import MainWindow
from app.gui.splash import show_splash
from app.widgets.app_header import AppHeader
from app.widgets.sidebar import Sidebar
from app.widgets.buttons import (
    DangerButton, PrimaryButton, SecondaryButton, ToolbarButton,
    inferred_button_role,
)


def test_reusable_button_roles(qtbot):
    for cls, role in (
        (PrimaryButton, "primary"),
        (SecondaryButton, "secondary"),
        (DangerButton, "danger"),
        (ToolbarButton, "toolbar"),
    ):
        button = cls("Ação")
        qtbot.addWidget(button)
        assert button.property("buttonRole") == role
        assert button.minimumHeight() == 36


def test_main_window_dashboard_refresh_real_integration(qtbot, monkeypatch):
    window = MainWindow(get_settings())
    qtbot.addWidget(window)
    page = window.pages["dashboard"]
    controller = window._dashboard_controller
    calls = []
    original = controller.service.get_dashboard_summary

    def tracked(year, month):
        calls.append((year, month))
        return original(year, month)

    monkeypatch.setattr(controller.service, "get_dashboard_summary", tracked)
    window.show()
    qtbot.waitExposed(window)
    assert page.refresh_button.isEnabled()
    qtbot.mouseClick(page.refresh_button, Qt.MouseButton.LeftButton)
    assert calls == [page.selected_period()]
    assert "Dashboard atualizado" in page.status.text()


def test_official_branding_assets_load():
    assert ASSETS_DIR.name == "assets"
    assert OFFICIAL_LOGO.is_file()
    assert OFFICIAL_SPLASH.is_file()
    assert not official_icon().isNull()


def test_header_contains_logo_tagline_and_version(qtbot):
    header = AppHeader()
    qtbot.addWidget(header)
    assert header.logo.pixmap() is not None and not header.logo.pixmap().isNull()
    assert header.tagline.text() == "GESTÃO • CONTROLE • RESULTADOS"
    assert header.version.text() == "Versão 1.0.0"


def test_tagline_is_top_only_and_sidebar_selection_is_visible(qtbot):
    navigated = []
    sidebar = Sidebar(navigated.append)
    qtbot.addWidget(sidebar)
    assert not any(
        label.text() == "GESTÃO • CONTROLE • RESULTADOS"
        for label in sidebar.findChildren(QLabel)
    )
    assert sidebar.buttons["dashboard"].isChecked()
    qtbot.mouseClick(sidebar.buttons["metas"], Qt.MouseButton.LeftButton)
    assert sidebar.buttons["metas"].isChecked()
    assert not sidebar.buttons["dashboard"].isChecked()
    assert navigated == ["metas"]


def test_splash_and_main_window_use_official_icon(qtbot, qapp):
    splash = show_splash(qapp)
    assert splash is not None
    assert not splash.pixmap().isNull()
    splash.close()
    window = MainWindow(get_settings())
    qtbot.addWidget(window)
    assert not window.windowIcon().isNull()
    assert window.header.tagline.text() == "GESTÃO • CONTROLE • RESULTADOS"


def test_legacy_and_dialog_actions_receive_consistent_semantic_roles(qtbot):
    assert inferred_button_role(PrimaryButton("Salvar")) == "primary"
    assert inferred_button_role(SecondaryButton("Cancelar")) == "secondary"
    assert inferred_button_role(ToolbarButton("Aplicar filtro")) == "toolbar"
