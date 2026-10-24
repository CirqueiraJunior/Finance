from decimal import Decimal
from openpyxl import Workbook

from app.importers.historical_parser import HistoricalWorkbookParser


def test_budget_skips_formula_only_footer(tmp_path):
    path = tmp_path / "budget.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "Or\u00e7ado"
    sheet.append([
        "DESCRICAO", "CATEGORIA", "TIPO",
        "VALOR ORCADO", "ANO", "MES", "ORDEMMES",
    ])
    sheet.append([
        "Administrativo", "Administrativo", "Despesa",
        2501.11, 2025, "JAN", 1,
    ])
    sheet.append([
        None, None, None, None, None, None, "#N/A",
    ])
    book.save(path)

    result = HistoricalWorkbookParser().parse(path)

    assert not result.errors, result.errors
    assert result.total == Decimal("2501.11")
    assert len(result.data) == 1
