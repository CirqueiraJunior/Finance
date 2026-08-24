from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, description: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("contentPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(12)

        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        message = QLabel(description)
        message.setObjectName("pageDescription")
        message.setWordWrap(True)

        layout.addWidget(heading)
        layout.addWidget(message)
        layout.addStretch()
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

