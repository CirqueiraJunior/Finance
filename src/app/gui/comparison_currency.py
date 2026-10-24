"""Formatação monetária de prévias de importação (somente UI)."""

from decimal import Decimal, InvalidOperation


def format_brl(value):
    if value is None or value == "":
        return "-"

    if isinstance(value, bool):
        return str(value)

    text = str(value).strip()

    if text == "-":
        return "-"

    if text.startswith("R$") or text.startswith("-R$"):
        return text

    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return text

    if not number.is_finite():
        return text

    negative = number < 0
    number = abs(number)

    formatted = f"{number:,.2f}"
    formatted = formatted.replace(",", "@").replace(".", ",").replace("@", ".")

    return ("-R$ " if negative else "R$ ") + formatted
