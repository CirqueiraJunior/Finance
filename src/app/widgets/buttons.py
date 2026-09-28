"""Botões reutilizáveis da identidade visual do J.A. Finance."""

from PySide6.QtGui import QCursor
from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QAbstractButton, QPushButton


def apply_button_role(button: QAbstractButton, role: str) -> QAbstractButton:
    """Aplica um papel visual sem acoplar a página ao stylesheet."""
    button.setProperty("buttonRole", role)
    button.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
    button.setMinimumHeight(40)
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
    """Classifica semanticamente botoes legados e botoes nativos de dialogos."""
    text = button.text().strip().casefold()

    # A??es principais / confirma??o
    if text.startswith((
        "salvar",
        "novo",
        "nova",
        "importar",
        "gerar",
        "fazer backup",
        "entrar",
        "concluir",
        "criar",
        "adicionar",
    )):
        return "primary"

    # A??es de altera??o de estado que exigem aten??o
    if text.startswith((
        "ativar/inativar",
        "ativar / inativar",
        "ativar/desativar",
        "ativar / desativar",
        "desativar",
        "inativar",
    )):
        return "warning"

    # A??es destrutivas
    if text.startswith((
        "excluir",
        "remover",
        "apagar",
        "revogar",
    )):
        return "danger"

    # Consulta / valida??o / atualiza??o / diagn?stico
    if text.startswith((
        "consultar",
        "validar",
        "verificar",
        "atualizar",
        "analisar",
        "carregar",
        "status",
        "auditoria",
        "usu?rios",
        "usuarios",
        "consultar aliases",
    )):
        return "info"

    # Controles compactos de filtro
    if text.startswith((
        "aplicar filtro",
        "filtrar",
    )):
        return "toolbar"

    # Edi??o, sele??o, cancelamento e demais a??es neutras
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
