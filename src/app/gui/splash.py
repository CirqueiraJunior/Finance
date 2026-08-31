"""Splash institucional construída com componentes nativos do PySide6."""

from PySide6.QtCore import QEventLoop, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

from app.core.branding import OFFICIAL_LOGO


SPLASH_DURATION_MS = 2000


class FinanceSplash(QWidget):
    """Apresentação leve da marca, sem texto rasterizado."""

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.SplashScreen | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("financeSplash")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(600, 420)
        self.setStyleSheet("QWidget#financeSplash { background: #ffffff; }")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(42, 34, 42, 34)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("splashIcon")
        self.icon_label.setFixedSize(104, 104)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(OFFICIAL_LOGO))
        if not pixmap.isNull():
            self.icon_label.setPixmap(
                pixmap.scaled(
                    self.icon_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        self.title_label = self._label(
            "Finance", "splashTitle", "34px", "#003B71", 700
        )
        self.slogan_label = self._label(
            "Decisões inteligentes para grandes resultados.",
            "splashSlogan", "18px", "#4A5568"
        )
        self.version_label = self._label(
            "Versão 1.0.0", "splashVersion", "14px", "#6B7280"
        )
        self.signature_label = self._label(
            "J.A. Technology", "splashSignature", "14px", "#003B71", 600
        )

        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.title_label)
        layout.addWidget(self.slogan_label)
        layout.addWidget(self.version_label)
        layout.addWidget(self.signature_label)

    @staticmethod
    def _label(text: str, name: str, size: str, color: str, weight: int = 400) -> QLabel:
        label = QLabel(text)
        label.setObjectName(name)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(
            f"background: transparent; border: none; color: {color}; "
            f"font-size: {size}; font-weight: {weight};"
        )
        return label

    def finish(self, _window: QWidget) -> None:
        self.close()
        self.deleteLater()


def show_splash(application: QApplication) -> FinanceSplash | None:
    """Exibe a composição oficial quando o ícone homologado está disponível."""
    if not OFFICIAL_LOGO.is_file():
        return None
    splash = FinanceSplash()
    if splash.icon_label.pixmap() is None or splash.icon_label.pixmap().isNull():
        splash.deleteLater()
        return None
    splash.show()
    application.processEvents()
    return splash


def hold_splash(splash: FinanceSplash | None, duration_ms: int = SPLASH_DURATION_MS) -> None:
    """Mantém a splash responsiva pelo intervalo visual configurado."""
    if splash is None:
        return
    loop = QEventLoop()
    QTimer.singleShot(duration_ms, loop.quit)
    loop.exec()
