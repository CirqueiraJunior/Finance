from decimal import Decimal
from pathlib import Path

from app.gui.pages.boe import BoePage
from app.importers.boe_types import BOEParsedRow, BOEValidationResult
from app.models.boe_import import BOEImport


def test_boe_page_starts_with_safe_actions_disabled(qtbot):
    page = BoePage()
    qtbot.addWidget(page)

    assert not page.validate_button.isEnabled()
    assert not page.import_button.isEnabled()
    assert page.history_table.columnCount() == 6


def test_boe_page_displays_validation_result(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    result = BOEValidationResult(
        caminho_arquivo=Path("BOE - 07.26.xlsx"),
        nome_arquivo="BOE - 07.26.xlsx",
        periodo_ano=2026,
        periodo_mes=7,
        linhas=[BOEParsedRow(5, 7501, "CDL GOIANIA/GO", 100, Decimal("6.9300"))],
    )

    page.show_validation(result)

    text = page.validation_result.toPlainText()
    assert "Status: APROVADO" in text
    assert "Período: 07/2026" in text
    assert "R$ 6,93" in text


def test_boe_page_displays_import_history(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    imported = BOEImport(
        periodo_ano=2026,
        periodo_mes=7,
        nome_arquivo="BOE - 07.26.xlsx",
        caminho_origem="C:/imports/BOE - 07.26.xlsx",
        hash_arquivo="a" * 64,
        quantidade_entidades=77,
        quantidade_inconsistencias=1,
        valor_total=Decimal("21967.2684"),
        status="imported",
    )

    page.show_history([imported])

    assert page.history_table.rowCount() == 1
    assert page.history_table.item(0, 0).text() == "07/2026"
    assert page.history_table.item(0, 4).text() == "R$ 21.967,27"
