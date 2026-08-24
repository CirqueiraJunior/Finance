from datetime import date
from decimal import Decimal

from app.models.cashflow_entry import CashflowEntry


def make_manual_entry(
    *, year: int = 2026, month: int = 7, description: str = "Receita de teste"
) -> CashflowEntry:
    return CashflowEntry(
        periodo_ano=year,
        periodo_mes=month,
        data_lancamento=date(year, month, 15),
        descricao=description,
        tipo="RECEITA",
        origem="MANUAL",
        categoria="RECEITA_INDIRETA",
        valor=Decimal("100.1234"),
        boe_import_id=None,
    )
