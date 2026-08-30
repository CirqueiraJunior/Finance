"""Header institucional do Finance no padrão J.A. Technology."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from app.core.branding import OFFICIAL_LOGO
from app.core.version import __version__


class AppHeader(QFrame):
    def __init__(self, parent=None, *, user_name: str = "", user_role: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("appHeader")
        self.setFixedHeight(96)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 10, 28, 10)
        layout.setSpacing(18)

        self.logo = QLabel()
        self.logo.setObjectName("headerLogo")
        self.logo.setFixedSize(72, 72)
        self.logo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if OFFICIAL_LOGO.is_file():
            pixmap = QPixmap(str(OFFICIAL_LOGO))
            self.logo.setPixmap(
                pixmap.scaled(
                    self.logo.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )

        self.tagline = QLabel("GESTÃO • CONTROLE • RESULTADOS")
        self.tagline.setObjectName("headerTagline")

        self.user = QLabel(f"{user_name}\n{user_role}" if user_name else "")
        self.user.setObjectName("headerUser")
        self.user.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.user.setVisible(bool(user_name))

        self.logout_button = QPushButton("Sair")
        self.logout_button.setObjectName("headerLogout")
        self.logout_button.setVisible(bool(user_name))

        self.version = QLabel(f"Versão {__version__}")
        self.version.setObjectName("headerVersion")

        layout.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.tagline, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch()
        layout.addWidget(self.user, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.logout_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.version, 0, Qt.AlignmentFlag.AlignVCenter)
