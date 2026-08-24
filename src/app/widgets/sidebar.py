from collections.abc import Callable

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout, QWidget


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
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(8)

        brand = QLabel("J.A. Finance")
        brand.setObjectName("brand")
        layout.addWidget(brand)
        layout.addSpacing(24)

        for label, key in self.ITEMS:
            button = QPushButton(label)
            button.setObjectName("navigationButton")
            button.setProperty("pageKey", key)
            button.clicked.connect(
                lambda checked=False, page_key=key: on_navigate(page_key)
            )
            layout.addWidget(button)
        layout.addStretch()
