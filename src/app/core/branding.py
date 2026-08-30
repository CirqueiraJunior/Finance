"""Localização única dos assets oficiais do Finance."""

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget


ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets"
OFFICIAL_LOGO = ASSETS_DIR / "finance_icon.png"
OFFICIAL_SPLASH = ASSETS_DIR / "finance_splash.png"
APPLICATION_ICON = ASSETS_DIR / "finance_icon.ico"


def official_icon() -> QIcon:
    """Retorna o ícone oficial quando o asset aprovado estiver disponível."""
    source = APPLICATION_ICON if APPLICATION_ICON.is_file() else OFFICIAL_LOGO
    return QIcon(str(source)) if source.is_file() else QIcon()


def apply_application_icon(application: QApplication) -> None:
    icon = official_icon()
    if not icon.isNull():
        application.setWindowIcon(icon)


def apply_window_icon(window: QWidget) -> None:
    icon = official_icon()
    if not icon.isNull():
        window.setWindowIcon(icon)
