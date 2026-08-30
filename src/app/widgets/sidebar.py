from collections.abc import Callable

from PySide6.QtWidgets import QFrame, QPushButton, QVBoxLayout, QWidget


class Sidebar(QFrame):
    ITEMS = (
        ("Dashboard", "dashboard"),
        ("Financeiro", "financeiro"),
        ("Orçado x Realizado", "orcamento"),
        ("BOE", "boe"),
        ("Metas", "metas"),
        ("Cadastros", "cadastros"),
        ("Relatórios", "relatorios"),
        ("Administração", "administracao"),
    )

    def __init__(
        self,
        on_navigate: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 18, 16, 24)
        layout.setSpacing(10)

        self.buttons = {}
        for label, key in self.ITEMS:
            button = QPushButton(label)
            button.setObjectName("navigationButton")
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
        self.buttons["dashboard"].setChecked(True)

    def _activate(self, page_key: str, callback: Callable[[str], None]) -> None:
        self.buttons[page_key].setChecked(True)
        callback(page_key)
