from decimal import Decimal

from openpyxl import Workbook

from app.importers.historical_importer import HistoricalWorkbookImporter


def test_applied_balance_uses_monthly_category_not_initial_note(tmp_path):
    path = tmp_path / "financeiro_2025.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Lançamentos"
    sheet.append([])
    sheet.append([
        "Ano", "Mês", "Descrição",
        "Observação", "Categoria", "Tipo", "Valor", "BOE",
    ])
    sheet.append([
        2025, "JAN", None, "Saldo Inicial = Saldo Final de 2024",
        None, None, 17174.42, "Não",
    ])
    sheet.append([
        2025, "JAN", None, "Saldo Aplicado Inicial",
        None, None, 454734.88, "Não",
    ])
    sheet.append([
        2025, "JAN", "Saldo Aplicado", None,
        "Saldo Aplicado", "Saldo", 494778.72, "Não",
    ])
    sheet.append([
        2025, "FEV", "Saldo Aplicado", None,
        "Saldo Aplicado", "Saldo", 475050.49, "Não",
    ])
    workbook.save(path)

    preview = HistoricalWorkbookImporter().parse(path)
    applied = [
        row for row in preview.rows
        if row.get("balance_type") == "SALDO_APLICADO"
    ]
    initial = [
        row for row in preview.rows
        if row.get("balance_type") == "SALDO_INICIAL"
    ]

    assert not preview.errors, preview.errors
    assert {(r["year"], r["month"]): r["value"] for r in applied} == {
        (2025, 1): Decimal("494778.72"),
        (2025, 2): Decimal("475050.49"),
    }
    assert len(initial) == 1
    assert initial[0]["value"] == Decimal("17174.42")
    assert not any(
        row.get("value") == Decimal("454734.88")
        for row in preview.rows
    )
