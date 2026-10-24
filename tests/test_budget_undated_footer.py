from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from app.importers.historical_parser import HistoricalWorkbookParser


def test_budget_ignores_undated_footer_but_rejects_partial_period(tmp_path):
    path = tmp_path / "orcamento.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Or\u00e7ado"
    sheet.append([
        "DESCRICAO", "CATEGORIA", "TIPO", "VALOR ORCADO",
        "ANO", "MES", "ORDEMMES",
    ])
    sheet.append([
        "Administrativo", "Administrativo", "Despesa",
        2501.11, 2025, "JAN", 1,
    ])
    sheet.append([
        "Rodape", None, None, None, None, None, None,
    ])
    workbook.save(path)

    parser = HistoricalWorkbookParser()
    result = parser.parse(path)

    assert not result.errors, result.errors
    assert result.total == Decimal("2501.11")
    assert len(result.data) == 1

    sheet.cell(3, 5).value = 2025
    workbook.save(path)

    partial = parser.parse(path)
    assert partial.errors
