from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget


class ImportWorkflowSteps(QWidget):
    """Visual stages shared by Finance import screens."""

    STEPS = (
        "Selecionar",
        "Validar",
        "Comparar",
        "Confirmar",
        "Importar",
    )

    def __init__(self, parent=None, *, steps=None):
        super().__init__(parent)
        self.setObjectName("importWorkflowSteps")
        if steps is not None:
            if len(steps) not in (4, 5):
                raise ValueError("Workflow requires 4 or 5 stages.")
            self.STEPS = tuple(steps)
        self.buttons = []
        row = QHBoxLayout(self)
        row.setContentsMargins(4, 8, 4, 8)
        row.setSpacing(8)

        for index, name in enumerate(self.STEPS, start=1):
            label = QPushButton(f"{index}. {name}")
            label.setEnabled(False)
            self.buttons.append(label)
            label.setObjectName("importWorkflowStep")
            label.setMinimumHeight(48)
            label.setStyleSheet("""
                QPushButton#importWorkflowStep {
                    background-color: #FFFFFF;
                    color: #164A78;
                    border: 1px solid #CAD6E3;
                    border-radius: 9px;
                    padding: 8px 6px;
                    font-weight: 600;
                }
            """)
            row.addWidget(label, 1)
            if index < len(self.STEPS):
                arrow = QLabel("\u2192")
                arrow.setObjectName("importWorkflowArrow")
                row.addWidget(arrow)

    def configure_actions(
        self,
        *,
        on_select=None,
        on_validate=None,
        on_compare=None,
        on_confirm=None,
        on_import=None,
    ):
        """Connect module-specific actions to the shared toolbar."""
        if getattr(self, "_workflow_configured", False):
            raise RuntimeError(
                "Import workflow actions already configured."
            )

        if len(self.buttons) == 4:
            callbacks = (
                on_select,
                on_validate,
                on_compare,
                on_import,
            )
        elif len(self.buttons) == 5:
            callbacks = (
                on_select,
                on_validate,
                on_compare,
                on_confirm,
                on_import,
            )
        else:
            raise RuntimeError("Unexpected import workflow layout.")

        for callback in callbacks:
            if callback is not None and not callable(callback):
                raise TypeError(
                    "Each workflow action must be callable."
                )

        for button, callback in zip(self.buttons, callbacks):
            if callback is not None:
                button.clicked.connect(callback)

        self._workflow_configured = True

    def set_stage_enabled(self, stage, enabled):
        """Enable or disable a stage, without invoking its action."""
        if not isinstance(stage, int) or not 1 <= stage <= len(self.buttons):
            raise ValueError("Stage is outside the workflow.")
        self.buttons[stage - 1].setEnabled(bool(enabled))

    def reset_stages(self):
        """Disable all stages; allow selecting a new file."""
        for button in self.buttons:
            button.setEnabled(False)
        self.buttons[0].setEnabled(True)
