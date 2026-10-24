from pathlib import Path

from openpyxl import Workbook

from app.importers.historical_importer import HistoricalWorkbookImporter


def workbook(tmp_path, names):
    path = tmp_path / "oficial.xlsx"
    wb = Workbook()
    wb.active.title = names[0]
    for name in names[1:]:
        wb.create_sheet(name)
    wb.save(path)
    return path


def test_multiple_compatible_sheets_blocked(tmp_path):
    path = workbook(
        tmp_path, ["Orçado", "Financeiro", "Lançamentos"]
    )
    result = HistoricalWorkbookImporter().parse_cashflow(path)
    assert result.detected_type != "FLUXO_CAIXA"
    assert result.errors


def test_unrelated_sheet_is_not_selected(tmp_path):
    path = workbook(tmp_path, ["Orçado"])
    result = HistoricalWorkbookImporter().parse_cashflow(path)
    assert result.detected_type != "FLUXO_CAIXA"
