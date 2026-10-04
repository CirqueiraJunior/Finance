from decimal import Decimal

from app.gui.formatters import (
    format_currency,
    format_integer,
    format_number,
    format_percentage,
)


def test_official_numeric_presentation_formats() -> None:
    assert format_currency(Decimal("1482803.5600")) == "R$ 1.482.803,56"
    assert format_currency(Decimal("1423865.3600")) == "R$ 1.423.865,36"
    assert format_percentage(Decimal("96.0252")) == "96,03%"
    assert format_currency(Decimal("0")) == "R$ 0,00"
    assert format_currency(Decimal("-58938.2000")) == "R$ -58.938,20"
    assert format_currency(None) == "—"
    assert format_percentage(None) == "—"
    assert format_number(None) == "—"
    assert format_integer(None) == "—"
    assert format_integer(77) == "77"


def test_formatter_accepts_supported_numeric_types() -> None:
    assert format_number(1234, 2) == "1.234,00"
    assert format_number(1234.5, 2) == "1.234,50"
    assert format_integer(1234) == "1.234"
