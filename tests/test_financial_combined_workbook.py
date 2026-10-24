from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook

from app.importers.historical_importer import HistoricalWorkbookImporter


def test_financeiro_prioritizes_lancamentos_in_combined_workbook(
    tmp_path, monkeypatch
):
    path = tmp_path / "planilha_oficial.xlsx"
    wb = Workbook()
    wb.active.title = "Orçado"
    wb.create_sheet("Lançamentos")
    wb.save(path)

    importer = HistoricalWorkbookImporter()
    calls = []

    def fake_cashflow(file_path, sheet):
        calls.append(sheet.title)
        return SimpleNamespace(detected_type="FLUXO_CAIXA", rows=[])

    monkeypatch.setattr(importer, "_cashflow", fake_cashflow)

    result = importer.parse_cashflow(path)

    assert result.detected_type == "FLUXO_CAIXA"
    assert calls == ["Lançamentos"]


def test_legacy_parse_interface_is_preserved():
    assert callable(HistoricalWorkbookImporter.parse)
    assert callable(HistoricalWorkbookImporter.parse_cashflow)
