from app.widgets.decimal_edit import BrazilianDecimalEdit


class BRLCurrencyEdit(BrazilianDecimalEdit):
    """Entrada monetária brasileira com prefixo R$."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent, prefix="R$")
