from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLineEdit


class BrazilianDecimalEdit(QLineEdit):
    """Entrada decimal brasileira em centavos, sem conversão por float."""

    def __init__(self, parent=None, *, prefix: str = "") -> None:
        super().__init__(parent)
        self._prefix = prefix
        self._show_digits("")

    def keyPressEvent(self, event) -> None:
        if event.key() in {Qt.Key.Key_Backspace, Qt.Key.Key_Delete}:
            digits = "".join(character for character in self.text() if character.isdigit())
            self._show_digits(
                digits[:-1] if event.key() == Qt.Key.Key_Backspace else ""
            )
            return
        typed_digits = "".join(
            character for character in event.text() if character.isdigit()
        )
        if typed_digits:
            current = "" if self.hasSelectedText() else "".join(
                character for character in self.text() if character.isdigit()
            )
            self._show_digits(current + typed_digits)
            return
        if (
            event.modifiers() & Qt.KeyboardModifier.ControlModifier
            and event.key() in {Qt.Key.Key_A, Qt.Key.Key_V}
        ):
            if event.key() == Qt.Key.Key_A:
                self.selectAll()
            return
        if event.text():
            return
        super().keyPressEvent(event)

    def clear(self) -> None:
        self._show_digits("")

    def _show_digits(self, digits: str) -> None:
        cents = int(digits or "0")
        whole, fraction = divmod(cents, 100)
        grouped = f"{whole:,}".replace(",", ".")
        separator = " " if self._prefix else ""
        self.setText(f"{self._prefix}{separator}{grouped},{fraction:02d}")
        self.setCursorPosition(len(self.text()))

    def decimal_value(self) -> Decimal:
        text = self.text().strip()
        if self._prefix and text.startswith(self._prefix):
            text = text[len(self._prefix):].strip()
        return Decimal(text.replace(".", "").replace(",", "."))

    def set_decimal_value(self, value: Decimal | str) -> None:
        amount = Decimal(value).quantize(Decimal("0.01"))
        cents = int(amount * 100)
        if cents < 0:
            raise ValueError("O componente não aceita valor negativo.")
        self._show_digits(str(cents))
