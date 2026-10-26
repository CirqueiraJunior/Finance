from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QPushButton, QWidget


class SettingsNavigation(QWidget):
    """Navegação interna da Central de Configurações."""

    section_changed = Signal(str)

    SECTIONS = (
        ("account", "Minha Conta"),
        ("security", "Segurança e Privacidade"),
        ("users", "Gestão de Usuários"),
        ("system", "Sistema e Atualizações"),
        ("parameters", "Parâmetros de Premiação"),
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._buttons = {}
        self._current_section = "account"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.setFixedWidth(255)

        for key, label in self.SECTIONS:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setMinimumHeight(36)
            button.clicked.connect(
                lambda checked=False, section=key: self.select_section(section)
            )
            layout.addWidget(button)
            self._buttons[key] = button

        layout.addStretch()
        self._refresh_selection()

    def select_section(self, section: str) -> None:
        if section not in self._buttons:
            raise ValueError(f"Seção desconhecida: {section}")

        if self._buttons[section].isHidden() or not self._buttons[section].isEnabled():
            return

        self._current_section = section
        self._refresh_selection()
        self.section_changed.emit(section)

    def set_section_available(self, section: str, available: bool) -> None:
        if section not in self._buttons:
            raise ValueError(f"Seção desconhecida: {section}")

        self._buttons[section].setVisible(available)
        self._buttons[section].setEnabled(available)

        if not available and self._current_section == section:
            self._current_section = "account"
            self._refresh_selection()
            self.section_changed.emit("account")

    def _refresh_selection(self) -> None:
        for key, button in self._buttons.items():
            selected = key == self._current_section
            button.setChecked(selected)
            button.setProperty("buttonRole", "primary" if selected else "secondary")
            button.style().unpolish(button)
            button.style().polish(button)

    @property
    def current_section(self) -> str:
        return self._current_section