"""Botões reutilizáveis da identidade visual do J.A. Finance."""

from PySide6.QtGui import QCursor
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractButton, QPushButton


def apply_button_role(button: QAbstractButton, role: str) -> QAbstractButton:
    """Aplica um papel visual sem acoplar a página ao stylesheet."""
    button.setProperty("buttonRole", role)
    button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    button.setMinimumHeight(36)
    return button


class _RoleButton(QPushButton):
    role = "secondary"

    def __init__(self, text: str = "", parent=None) -> None:
        super().__init__(text, parent)
        apply_button_role(self, self.role)


class PrimaryButton(_RoleButton):
    role = "primary"


class SecondaryButton(_RoleButton):
    role = "secondary"


class DangerButton(_RoleButton):
    role = "danger"


class ToolbarButton(_RoleButton):
    role = "toolbar"


def inferred_button_role(button: QAbstractButton) -> str:
    """Classifica controles legados e botões nativos de diálogos."""
    text = button.text().strip().casefold()
    if text.startswith(("salvar", "novo", "nova", "importar", "gerar", "fazer backup")):
        return "primary"
    if text.startswith(("atualizar", "aplicar filtro", "consultar", "validar", "analisar")):
        return "toolbar"
    return "secondary"


class ButtonStyleFilter(QObject):
    """Garante o padrão também em diálogos criados depois da MainWindow."""

    def eventFilter(self, watched, event) -> bool:
        if (
            isinstance(watched, QAbstractButton)
            and watched.objectName() != "navigationButton"
            and event.type() in (QEvent.Type.Polish, QEvent.Type.Show)
            and not watched.property("buttonRole")
        ):
            apply_button_role(watched, inferred_button_role(watched))
        return super().eventFilter(watched, event)
