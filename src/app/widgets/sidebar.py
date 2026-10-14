from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget


class Sidebar(QFrame):
    ITEMS = (
        ("dashboard", "Dashboard", "dashboard"),
        ("financeiro", "Financeiro", "financeiro"),
        ("orcamento", "Orçado x Realizado", "orcamento"),
        ("boe", "BOE", "boe"),
        ("metas", "Metas", "metas"),
        ("cadastros", "Cadastros", "cadastros"),
        ("relatorios", "Relatórios", "relatorios"),
        ("administracao", "Administração", "administracao"),
    )

    def __init__(
        self,
        on_navigate: Callable[[str], None],
        parent: QWidget | None = None,
        *,
        allowed_pages: set[str] | None = None,
        on_logout: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)

        # JA_TECH_FINANCE_SIDEBAR_V1
        self.setStyleSheet("""
            QFrame#sidebar {
                background-color: #FFFFFF;
                border: none;
            }

            QFrame#sidebar QPushButton#navigationButton,
            QFrame#sidebar QPushButton#sidebarActionButton {
                background-color: #EDF5FC;
                color: #003B71;
                border: 1px solid #CBD5E1;
                border-left: 5px solid #4C8FC0;
                border-radius: 10px;
                padding: 10px 9px;
                min-height: 28px;
                text-align: left;
                font-weight: 600;
            }

            QFrame#sidebar QPushButton#navigationButton:hover,
            QFrame#sidebar QPushButton#sidebarActionButton:hover {
                background-color: #FFFFFF;
                border-color: #8CB6D9;
            }

            QFrame#sidebar QPushButton#navigationButton:checked {
                background-color: #DCECF9;
                color: #003B71;
                border: 1px solid #8CB6D9;
                border-left: 5px solid #D6A400;
                font-weight: 700;
            }

            QFrame#sidebar QPushButton#navigationButton:disabled {
                background-color: #F2F4F7;
                color: #98A2AD;
                border-color: #D9DEE5;
            }

            QFrame#sidebar QPushButton#navigationButton[pageKey="financeiro"] {
                background-color: #EDF7F5;
                color: #176D66;
                border-left-color: #42978E;
            }

            QFrame#sidebar QPushButton#navigationButton[pageKey="orcamento"] {
                background-color: #EEF5FA;
                border-left-color: #4C8FC0;
            }

            QFrame#sidebar QPushButton#navigationButton[pageKey="boe"] {
                background-color: #F3F1FB;
                color: #4D508E;
                border-left-color: #7778C8;
            }

            QFrame#sidebar QPushButton#navigationButton[pageKey="metas"] {
                background-color: #FFF7DF;
                color: #745800;
                border-left-color: #D6A400;
            }

            QFrame#sidebar QPushButton#navigationButton[pageKey="cadastros"] {
                background-color: #F4F6F8;
                color: #475569;
                border-left-color: #91A3B0;
            }

            QFrame#sidebar QPushButton#navigationButton[pageKey="relatorios"] {
                background-color: #EEF5FA;
                border-left-color: #4C8FC0;
            }

            QFrame#sidebar QPushButton#navigationButton[pageKey="administracao"] {
                background-color: #F4F6F8;
                color: #475569;
                border-left-color: #AAB7C4;
            }

            QFrame#sidebar QPushButton#navigationButton:checked {
                background-color: #DCECF9;
                color: #003B71;
                border-left-color: #D6A400;
                font-weight: 700;
            }

            QFrame#sidebar QPushButton#sidebarActionButton {
                background-color: #FFFFFF;
                color: #475569;
                border-left-color: #91A3B0;
            }

            QFrame#sidebar QPushButton#sidebarActionButton:hover {
                background-color: #F1F5F9;
            }

            QFrame#sidebar QFrame#sidebarSeparator {
                background-color: #D6DEE8;
                border: none;
            }
        """)

        self._icons_dir = (
            Path(__file__).resolve().parents[1]
            / "resources"
            / "icons"
            / "sidebar"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 16, 14, 18)
        layout.setSpacing(5)

        self.buttons = {}

        for icon_name, label, key in self.ITEMS:
            button = self._make_button(
                label,
                icon_name,
                object_name="navigationButton",
            )
            button.setProperty("pageKey", key)
            button.setCheckable(True)
            button.setAutoExclusive(True)
            button.clicked.connect(
                lambda checked=False, page_key=key: self._activate(
                    page_key, on_navigate
                )
            )
            self.buttons[key] = button
            layout.addWidget(button)

        layout.addStretch()

        separator = QFrame()
        separator.setObjectName("sidebarSeparator")
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(1)
        layout.addWidget(separator)

        self.help_button = self._make_button(
            "Ajuda", "ajuda", object_name="sidebarActionButton"
        )
        self.help_button.clicked.connect(lambda: on_navigate("__help__"))
        layout.addWidget(self.help_button)

        self.logout_button = self._make_button(
            "Sair", "sair", object_name="sidebarActionButton"
        )
        if on_logout is not None:
            self.logout_button.clicked.connect(on_logout)
        layout.addWidget(self.logout_button)

        self.set_allowed_pages(
            set(self.buttons if allowed_pages is None else allowed_pages)
        )

    def _make_button(
        self,
        text: str,
        icon_name: str,
        *,
        object_name: str,
    ) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        source_icon = QIcon(str(self._icons_dir / f"{icon_name}.svg"))
        pixmap = source_icon.pixmap(QSize(18, 18))
        if not pixmap.isNull():
            painter = QPainter(pixmap)
            painter.setCompositionMode(
                QPainter.CompositionMode.CompositionMode_SourceIn
            )
            painter.fillRect(pixmap.rect(), QColor("#003B71"))
            painter.end()
            button.setIcon(QIcon(pixmap))
        else:
            button.setIcon(source_icon)
        button.setIconSize(QSize(18, 18))
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    def set_allowed_pages(self, allowed_pages: set[str]) -> None:
        allowed = set(allowed_pages)
        first_visible = None

        for key, button in self.buttons.items():
            visible = key in allowed
            button.setVisible(visible)
            button.setEnabled(visible)
            button.setChecked(False)

            if visible and first_visible is None:
                first_visible = button

        if first_visible is not None:
            first_visible.setChecked(True)

    def select_page(self, page_key: str) -> None:
        button = self.buttons.get(page_key)
        if button is not None and not button.isHidden():
            button.setChecked(True)

    def _activate(self, page_key: str, callback: Callable[[str], None]) -> None:
        self.buttons[page_key].setChecked(True)
        callback(page_key)
