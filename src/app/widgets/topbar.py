from PySide6.QtWidgets import QFrame, QLabel, QHBoxLayout, QWidget


class TopBar(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topbar")
        self.setFixedHeight(64)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 0, 24, 0)
        label = QLabel(title)
        label.setObjectName("topbarTitle")
        layout.addWidget(label)
        layout.addStretch()
