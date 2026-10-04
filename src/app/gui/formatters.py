from decimal import Decimal
from typing import Any


PLACEHOLDER = "—"


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def format_number(value: Any, decimals: int = 2) -> str:
    if value is None:
        return PLACEHOLDER
    formatted = f"{_decimal(value):,.{decimals}f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")


def format_currency(value: Any) -> str:
    if value is None:
        return PLACEHOLDER
    return f"R$ {format_number(value, 2)}"


def format_percentage(value: Any) -> str:
    if value is None:
        return PLACEHOLDER
    return f"{format_number(value, 2)}%"


def format_integer(value: Any) -> str:
    if value is None:
        return PLACEHOLDER
    return f"{int(_decimal(value)):,}".replace(",", ".")
