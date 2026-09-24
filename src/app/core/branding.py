"""Localização única dos assets oficiais homologados do Finance."""

from pathlib import Path
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QWidget


def _runtime_root() -> Path:
    """Resolve recursos tanto em DEV quanto no execut?vel PyInstaller."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parents[3]


PROJECT_ROOT = _runtime_root()
BRANDING_DIR = PROJECT_ROOT / "assets" / "branding"
OFFICIAL_LOGO = BRANDING_DIR / "finance_icon_FINAL.png"
OFFICIAL_MARK = BRANDING_DIR / "finance_mark_transparent_FINAL.png"
DESKTOP_ICON_PNG = BRANDING_DIR / "finance_desktop_v100.png"
APPLICATION_ICON = BRANDING_DIR / "finance_desktop_v100.ico"
SPLASH_REFERENCE = BRANDING_DIR / "finance_splash_reference.png"


def official_icon() -> QIcon:
    """Retorna o ícone oficial quando o asset aprovado estiver disponível."""
    source = APPLICATION_ICON if APPLICATION_ICON.is_file() else DESKTOP_ICON_PNG
    return QIcon(str(source)) if source.is_file() else QIcon()


def apply_application_icon(application: QApplication) -> None:
    icon = official_icon()
    if not icon.isNull():
        application.setWindowIcon(icon)


def apply_window_icon(window: QWidget) -> None:
    icon = official_icon()
    if not icon.isNull():
        window.setWindowIcon(icon)
