"""Shared visual container for Finance import workflows."""

from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)


class ImportWorkflowPanel(QWidget):
    """BOE-style layout with module-provided controls and results."""

    def __init__(
        self,
        *,
        steps,
        file_display,
        results_layout,
        preview=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setObjectName("importWorkflowPanel")

        self.steps = steps
        self.file_display = file_display
        self.preview = preview

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        layout.addWidget(steps)

        if isinstance(file_display, QLabel):
            file_display.setObjectName("importWorkflowFile")
            file_display.setMinimumHeight(40)
            file_display.setStyleSheet(
                "QLabel#importWorkflowFile {"
                "background-color: white;"
                "border: 1px solid #CAD6E3;"
                "border-radius: 7px;"
                "padding: 8px 12px;"
                "color: #44546A;"
                "}"
            )

        layout.addWidget(file_display)
        layout.addLayout(results_layout)

        if preview is not None:
            layout.addWidget(preview)

    def add_footer(self, widget):
        """Place the operation status after the optional preview."""
        self.layout().addWidget(widget)
