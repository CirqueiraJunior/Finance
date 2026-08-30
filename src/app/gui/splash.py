"""Splash não bloqueante baseado exclusivamente no asset oficial aprovado."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QSplashScreen

from app.core.branding import OFFICIAL_SPLASH


def show_splash(application: QApplication) -> QSplashScreen | None:
    """Exibe o splash se o asset Opção 03 existir; não cria substituto visual."""
    if not OFFICIAL_SPLASH.is_file():
        return None
    pixmap = QPixmap(str(OFFICIAL_SPLASH))
    if pixmap.isNull():
        return None
    pixmap = pixmap.scaledToHeight(
        700, Qt.TransformationMode.SmoothTransformation
    )
    splash = QSplashScreen(pixmap)
    splash.show()
    application.processEvents()
    return splash
