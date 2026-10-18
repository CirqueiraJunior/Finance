"""Confirmação reutilizável de importação acionada pela interface gráfica.

Não substitui a validação/revalidação transacional no servidor.
"""
from PySide6.QtWidgets import QMessageBox, QWidget


def confirm_import(parent: QWidget, *, module_name: str) -> bool:
    result = QMessageBox.question(
        parent,
        "Confirmar importação",
        (
            f"Confirma a importação de {module_name}?\n\n"
            "Os registros poderão ser incluídos ou atualizados conforme "
            "a validação apresentada.\n"
            "O arquivo Excel original não será modificado."
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return result == QMessageBox.StandardButton.Yes