from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

from app.core.branding import (
    APPLICATION_ICON,
    BRANDING_DIR,
    DESKTOP_ICON_PNG,
    OFFICIAL_LOGO,
    OFFICIAL_MARK,
    SPLASH_REFERENCE,
    official_icon,
)
from app.core.config import get_settings
from app.gui.main_window import MainWindow
from app.gui.splash import FinanceSplash, SPLASH_DURATION_MS, show_splash
from app.resources import load_stylesheet
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


def test_main_window_dashboard_refresh_real_integration(qtbot, monkeypatch, isolated_app_database):
    window = MainWindow(get_settings())
    qtbot.addWidget(window)
    page = window.pages["dashboard"]
    controller = window._dashboard_controller
    calls = []
    def tracked(year, month, **filters):
        calls.append((year, month))
        return {}

    monkeypatch.setattr(controller.service, "get_dashboard_data", tracked)
    window.show()
    qtbot.waitExposed(window)
    assert page.refresh_button.isEnabled()
    qtbot.mouseClick(page.refresh_button, Qt.MouseButton.LeftButton)
    assert calls == [page.selected_period()]
    assert "Dashboard atualizado" in page.status.text()


def test_official_branding_assets_load():
    assert BRANDING_DIR.parts[-2:] == ("assets", "branding")
    assert OFFICIAL_LOGO.name == "finance_icon_FINAL.png"
    assert OFFICIAL_MARK.name == "finance_mark_transparent_FINAL.png"
    assert DESKTOP_ICON_PNG.name == "finance_desktop_v100.png"
    assert APPLICATION_ICON.name == "finance_desktop_v100.ico"
    assert SPLASH_REFERENCE.name == "finance_splash_reference.png"
    assert all(path.is_file() for path in (
        OFFICIAL_LOGO, OFFICIAL_MARK, DESKTOP_ICON_PNG,
        APPLICATION_ICON, SPLASH_REFERENCE,
    ))
    assert not official_icon().isNull()


def test_header_contains_logo_tagline_and_version(qtbot):
    header = AppHeader()
    qtbot.addWidget(header)
    assert not hasattr(header, "change_password_button")
    margins = header.layout().contentsMargins()
    assert header.height() == 64
    assert (margins.left(), margins.top(), margins.right(), margins.bottom()) == (
        12, 6, 12, 6,
    )
    assert header.layout().spacing() == 16
    assert header.logo.size().width() == 52
    assert header.logo.size().height() == 52
    assert header.logo.pixmap() is not None and not header.logo.pixmap().isNull()
    assert header.tagline.text() == "Gestão • Controle • Resultados"
    assert header.version.text() == "Versão 1.0.0"


def test_tagline_is_top_only_and_sidebar_selection_is_visible(qtbot):
    navigated = []
    sidebar = Sidebar(navigated.append)
    qtbot.addWidget(sidebar)
    assert not any(
        label.text() == "Gestão • Controle • Resultados"
        for label in sidebar.findChildren(QLabel)
    )
    assert sidebar.buttons["dashboard"].isChecked()
    qtbot.mouseClick(sidebar.buttons["metas"], Qt.MouseButton.LeftButton)
    assert sidebar.buttons["metas"].isChecked()
    assert not sidebar.buttons["dashboard"].isChecked()
    assert navigated == ["metas"]


def test_splash_and_main_window_use_official_icon(qtbot, qapp, isolated_app_database):
    splash = show_splash(qapp)
    assert splash is not None
    assert isinstance(splash, FinanceSplash)
    assert splash.size().width() == 520
    assert splash.size().height() == 360
    assert splash.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    assert splash.testAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
    assert not splash.autoFillBackground()
    assert splash.layout().contentsMargins().left() == 36
    assert splash.layout().contentsMargins().top() == 30
    assert splash.layout().contentsMargins().right() == 36
    assert splash.layout().contentsMargins().bottom() == 30
    assert splash.layout().spacing() == 10
    assert splash.icon_label.size().width() == 92
    assert splash.icon_label.size().height() == 92
    assert not splash.icon_label.pixmap().isNull()
    assert splash.title_label.text() == "Finance"
    assert "font-size: 30px" in splash.title_label.styleSheet()
    assert "font-weight: 700" in splash.title_label.styleSheet()
    assert "color: #003B71" in splash.title_label.styleSheet()
    assert splash.slogan_label.text() == "Decisões inteligentes para grandes resultados."
    assert "font-size: 16px" in splash.slogan_label.styleSheet()
    assert "color: #4A5568" in splash.slogan_label.styleSheet()
    assert splash.version_label.text() == "Versão 1.0.0"
    assert "font-size: 13px" in splash.version_label.styleSheet()
    assert "color: #6B7280" in splash.version_label.styleSheet()
    assert splash.signature_label.text() == "J.A. Technology"
    assert "font-size: 13px" in splash.signature_label.styleSheet()
    assert "font-weight: 600" in splash.signature_label.styleSheet()
    assert "color: #003B71" in splash.signature_label.styleSheet()
    assert SPLASH_DURATION_MS == 2000
    splash.close()
    window = MainWindow(get_settings())
    qtbot.addWidget(window)
    assert not window.windowIcon().isNull()
    assert window.header.tagline.text() == "Gestão • Controle • Resultados"


def test_splash_is_composed_and_reference_is_not_rendered(qtbot):
    splash = FinanceSplash()
    qtbot.addWidget(splash)
    assert splash.findChild(QLabel, "splashIcon") is splash.icon_label
    assert SPLASH_REFERENCE.name not in splash.styleSheet()


def test_page_heading_styles_use_official_visual_values():
    stylesheet = load_stylesheet()
    assert 'font-family: "Segoe UI";' in stylesheet
    assert "font-size: 18px;" in stylesheet
    assert "font-weight: 600;" in stylesheet
    assert "letter-spacing: 0px;" in stylesheet
    assert "QLabel#pageTitle { color: #003B71; font-size: 30px; font-weight: 700; }" in stylesheet
    assert "QLabel#pageDescription { color: #4A5568; font-size: 16px; }" in stylesheet


def test_legacy_and_dialog_actions_receive_consistent_semantic_roles(qtbot):
    assert inferred_button_role(PrimaryButton("Salvar")) == "primary"
    assert inferred_button_role(SecondaryButton("Cancelar")) == "secondary"
    assert inferred_button_role(ToolbarButton("Aplicar filtro")) == "toolbar"
