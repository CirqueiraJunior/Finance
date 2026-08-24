from decimal import Decimal

from app.importers.boe_importer import BOEImporter
from app.importers.boe_types import BOEIssueSeverity
from tests.boe_helpers import DEFAULT_ROWS, create_boe_workbook


def test_importer_parses_valid_hierarchical_workbook(tmp_path) -> None:
    path = create_boe_workbook(tmp_path / "BOE - 07.26.xlsx")

    result = BOEImporter().parse(path)

    assert result.aprovado is True
    assert (result.periodo_mes, result.periodo_ano) == (7, 2026)
    assert len(result.linhas) == 2
    assert result.linhas[0].codigo_entidade == 7501
    assert result.linhas[0].valor_total == Decimal("6.9300")
    assert result.hash_arquivo is not None
    assert len(result.hash_arquivo) == 64


def test_importer_rejects_missing_sheet(tmp_path) -> None:
    path = create_boe_workbook(
        tmp_path / "BOE - 07.26.xlsx", sheet_name="Outra aba"
    )

    result = BOEImporter().parse(path)

    assert result.aprovado is False
    assert any("Taxa BOE" in issue.mensagem for issue in result.inconsistencias)


def test_importer_rejects_invalid_structure(tmp_path) -> None:
    path = create_boe_workbook(
        tmp_path / "BOE - 07.26.xlsx", valid_headers=False
    )

    result = BOEImporter().parse(path)

    assert result.aprovado is False
    assert any("cabeçalhos" in issue.mensagem for issue in result.inconsistencias)


def test_importer_ignores_code_7500_as_consolidated(tmp_path) -> None:
    path = create_boe_workbook(
        tmp_path / "BOE - 07.26.xlsx", include_consolidated=True
    )

    result = BOEImporter().parse(path)

    assert result.aprovado is True
    assert all(row.codigo_entidade != 7500 for row in result.linhas)
    assert result.quantidade_consolidada == 150
    assert result.valor_consolidado == Decimal("10.3950")
    assert any(
        issue.severidade is BOEIssueSeverity.WARNING and issue.codigo == "7500"
        for issue in result.inconsistencias
    )


def test_importer_prioritizes_period_inside_workbook(tmp_path) -> None:
    path = create_boe_workbook(
        tmp_path / "BOE - 07.26.xlsx",
        explicit_period="Competência: 06/2026",
    )

    result = BOEImporter().parse(path)

    assert (result.periodo_mes, result.periodo_ano) == (6, 2026)


def test_importer_rejects_negative_values(tmp_path) -> None:
    rows = [(7501, "CDL GOIANIA/GO", -1, Decimal("-0.0693"))]
    path = create_boe_workbook(tmp_path / "BOE - 07.26.xlsx", rows=rows)

    result = BOEImporter().parse(path)

    assert result.aprovado is False
    assert result.quantidade_erros == 3


def test_importer_ignores_empty_rows(tmp_path) -> None:
    path = create_boe_workbook(
        tmp_path / "BOE - 07.26.xlsx", blank_rows=True
    )

    result = BOEImporter().parse(path)

    assert result.aprovado is True
    assert [row.codigo_entidade for row in result.linhas] == [7501, 7544]
    assert sum(row.quantidade_consultas for row in result.linhas) == sum(
        row[2] for row in DEFAULT_ROWS
    )
