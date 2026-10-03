from decimal import Decimal
import inspect

from openpyxl import Workbook, load_workbook

import app.importers.historical_parser as parser_module
from app.importers.historical_importer import HistoricalWorkbookImporter
from app.importers.historical_parser import (
    AssociationImportData, BudgetImportData, HistoricalWorkbookParser,
    TargetImportData,
)
from app.models.entity import Entity
from app.repositories.entity_repository import EntityRepository
from app.services.entity_service import EntityService
from app.services.historical_import_service import HistoricalImportService


def _target_workbook(path) -> None:
    workbook = Workbook()
    target = workbook.active
    target.title = "Meta"
    target.append([])
    target.append([])
    target.append(["COD.", "Entidade", "JAN"])
    target.append([7500, "Consolidado", 999])
    target.append([7001, "Entidade inativa", 100])
    actual = workbook.create_sheet("Faturamento")
    actual.append([])
    actual.append([])
    actual.append(["COD.", "Entidade", "JAN"])
    actual.append([7500, "Consolidado", 999])
    actual.append([7001, "Entidade inativa", 80])
    workbook.save(path)


def _budget_workbook(path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Planej. orçamentário"
    for _ in range(8):
        sheet.append([])
    for label, value in (
        ("Repasse CDLs Estado Goiás", 200),
        ("Despesas com Pessoal", 100),
        ("Despesas com Eventos", 50),
        ("Despesas com a Operação", 25),
        ("Software", 999),
        ("Viagem", 999),
        ("Impostos e Taxas", 999),
        ("Aplicação", 999),
        ("Resgate", 999),
        ("Saldo", 999),
    ):
        sheet.append([None, label, value, None])
    workbook.save(path)


def _official_multiyear_workbook(
    path, *, actual_sheet="Faturamento", association_sheet="Associações",
    association_header_row=1, internal_year=None, capture_header="CAPTAÇÃO",
) -> None:
    workbook = Workbook()
    target = workbook.active
    target.title = "Planejamento oficial"
    target.append(["META DE CONSULTAS"])
    target.append(["COD.", "ENTIDADES", "JAN", "FEV"])
    target.append([7501, "Goiânia", 100, 110])
    target.append(["META DE REGISTROS"])
    target.append(["COD", "ENTIDADE", "JAN", "FEV"])
    target.append([7501, "Goiânia", 20, 25])

    actual = workbook.create_sheet(actual_sheet)
    actual.append(["CONSULTAS REALIZADAS"])
    actual.append(["COD", "ENTIDADE", "JAN", "FEV"])
    actual.append([7501, "Goiânia", 80, 90])
    actual.append(["REGISTROS REALIZADOS"])
    actual.append(["COD.", "ENTIDADES", "JAN", "FEV"])
    actual.append([7501, "Goiânia", 15, 18])

    associations = workbook.create_sheet(association_sheet)
    for _ in range(association_header_row - 1):
        associations.append([])
    month_names = (
        "JANEIRO", "FEVEREIRO", "MARÇO", "ABRIL", "MAIO", "JUNHO",
        "JULHO", "AGOSTO", "SETEMBRO", "OUTUBRO", "NOVEMBRO", "DEZEMBRO",
    )
    month_row = ["COD", "ENTIDADES"] + [None] * 48
    subheader_row = [None, None] + [None] * 48
    for month, name in enumerate(month_names):
        base = 2 + month * 4
        month_row[base] = name
        subheader_row[base:base + 4] = [
            "CANC.", capture_header, "SUSPENSO", "TOTAL ASSC"
        ]
    associations.append(month_row)
    associations.append(subheader_row)
    values = [7501, "Goiânia"] + [None] * 48
    values[2:6] = [5, 10, 1, 100]
    associations.append(values)

    if internal_year is not None:
        title = workbook.create_sheet("Visão Entidade")
        title["B2"] = f"META X REALIZADO {internal_year}"
    workbook.save(path)


def test_parser_is_pure_and_has_no_database_or_persistence_dependencies(tmp_path):
    path = tmp_path / "Meta x Realizado 2026.xlsx"
    _target_workbook(path)

    result = HistoricalWorkbookParser().parse(path)

    source = inspect.getsource(parser_module).casefold()
    assert "sqlalchemy" not in source
    assert "session" not in source
    assert "repository" not in source
    assert "commit(" not in source
    assert result.can_import
    assert isinstance(result.data[0], TargetImportData)


def test_target_parser_excludes_non_entity_7500_and_7600_and_preserves_values(tmp_path):
    path = tmp_path / "Meta x Realizado 2026.xlsx"
    _target_workbook(path)

    result = HistoricalWorkbookParser().parse(path)

    assert result.metadata.detected_type == "META_REALIZADO"
    assert result.metadata.year == 2026
    assert {(row.code, row.indicator, row.target, row.actual) for row in result.data} == {
        (7001, "CONSULTAS", Decimal("100.0000"), Decimal("80.0000"))
    }
    assert all(row.code != 7500 for row in result.data)
    assert result.warnings


def test_target_parser_accepts_unambiguous_year_and_region_sheet_suffixes(tmp_path):
    path = tmp_path / "Metas 2026 - GO.xlsm"
    workbook = Workbook()
    target = workbook.active
    target.title = "Meta 2026 - GO"
    target.append(["META DE CONSULTAS"])
    target.append([7500, "Consolidado", 999])
    target.append([7600, "FCDL", 999])
    target.append([7501, "Goiânia", 100])
    actual = workbook.create_sheet("Faturamento 2026 - GO")
    actual.append(["CONSULTAS REALIZADAS"])
    actual.append([7500, "Consolidado", 999])
    actual.append([7600, "FCDL", 999])
    actual.append([7501, "Goiânia", 80])
    workbook.save(path)

    result = HistoricalWorkbookParser().parse(path)

    assert result.metadata.detected_type == "META_REALIZADO"
    assert [(row.code, row.target, row.actual) for row in result.data] == [
        (7501, Decimal("100.0000"), Decimal("80.0000"))
    ]


def test_target_parser_supports_real_go_2026_structural_layout(tmp_path):
    path = tmp_path / "Metas 2026 - GO.xlsm"
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "GO - Metas 2026(Metas 2026)"
    sheet.append(["PLANEJAMENTO DE METAS 2026"])
    sheet.append(["Metas aprovadas no Conselho Nacional em 28/11/2025"])
    sheet.append([])
    sheet.append([
        "COD.", "ENTIDADE", "VERTENTE", "Jan", "Fev", "Mar",
        "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov",
        "Dez", "TOTAL ANUAL",
    ])
    monthly_7501 = list(range(101, 113))
    monthly_7503 = list(range(201, 213))
    sheet.append([7501, "CDL GOIANIA/GO-7501", "CONSULTAS", *monthly_7501, "=SUM(D5:O5)"])
    sheet.append(["7503", "CDL VALPARAISO DE GOIAS/GO-7503", "CONSULTAS", *monthly_7503, "=SUM(D6:O6)"])
    sheet.append([7500, "CONSOLIDADO", "CONSULTAS", *([999] * 12), "=SUM(D7:O7)"])
    sheet.append([7600, "FCDL", "CONSULTAS", *([888] * 12), "=SUM(D8:O8)"])
    workbook.save(path)

    result = HistoricalWorkbookParser().parse(path)

    assert result.metadata.detected_type == "META_REALIZADO"
    assert result.metadata.year == 2026
    assert len(result.data) == 24
    assert {row.code for row in result.data} == {7501, 7503}
    assert {row.entity_name for row in result.data} == {
        "CDL GOIANIA/GO-7501", "CDL VALPARAISO DE GOIAS/GO-7503",
    }
    assert [row.target for row in result.data if row.code == 7501] == [
        Decimal(f"{value}.0000") for value in monthly_7501
    ]
    assert all(row.actual == Decimal("0.0000") for row in result.data)
    assert all(row.code not in {7500, 7600} for row in result.data)


def test_budget_parser_keeps_only_current_operational_categories(tmp_path):
    path = tmp_path / "Projeção Orçamentária 2026.xlsx"
    _budget_workbook(path)

    result = HistoricalWorkbookParser().parse(path)

    assert result.metadata.detected_type == "ORCAMENTO"
    assert all(isinstance(row, BudgetImportData) for row in result.data)
    assert {(row.entry_type, row.category) for row in result.data} == {
        ("RECEITA", "RECEITA_DIRETA"),
        ("DESPESA", "PESSOAL"),
        ("DESPESA", "EVENTOS"),
        ("DESPESA", "OPERACIONAL"),
    }
    assert not {"SOFTWARE", "VIAGEM", "IMPOSTOS_E_TAXAS", "SALDO_APLICADO"}.intersection(
        row.category for row in result.data
    )
    assert result.total == Decimal("375.0000")


def test_budget_parser_accepts_future_year_from_filename(tmp_path):
    path = tmp_path / "Projeção Orçamentária 2027.xlsx"
    _budget_workbook(path)

    result = HistoricalWorkbookParser().parse(path)

    assert result.can_import
    assert result.metadata.detected_type == "ORCAMENTO"
    assert result.metadata.year == 2027
    assert all(row.year == 2027 for row in result.data)


def test_budget_parser_reports_missing_year_without_silent_2026_fallback(tmp_path):
    path = tmp_path / "Projeção Orçamentária.xlsx"
    _budget_workbook(path)

    result = HistoricalWorkbookParser().parse(path)

    assert not result.can_import
    assert result.metadata.detected_type == "DESCONHECIDO"
    assert result.metadata.year is None
    assert "Ano do Orçamento não identificado" in result.errors[0]


def test_local_service_consumes_parser_adapter_and_accepts_inactive_entity(
        db_session, tmp_path):
    path = tmp_path / "Meta x Realizado 2026.xlsx"
    _target_workbook(path)
    db_session.add(Entity(
        codigo_entidade=7001, nome="Entidade inativa", ativa=False,
    ))
    db_session.commit()
    service = HistoricalImportService(
        db_session,
        HistoricalWorkbookImporter(HistoricalWorkbookParser()),
        EntityService(EntityRepository(db_session)),
        None,
        None,
        None,
    )

    preview = service.analyze(path)

    assert preview.detected_type == "META_REALIZADO"
    assert preview.errors == []
    assert preview.valid_rows == 1
    assert preview.rows[0]["entity_id"] is not None


def test_target_parser_separates_official_query_and_registration_sections(tmp_path):
    path = tmp_path / "Meta x Realizado - Oficial 2026.xlsm"
    workbook = Workbook()
    target = workbook.active
    target.title = "Meta"
    target.append(list(range(1, 15)))
    target.append(["META DE CONSULTAS"])
    target.append(["COD.", "Entidade", "JAN", "FEV"])
    target.append([7501, "Goiânia", 100, 110])
    target.append([])
    target.append(list(range(1, 15)))
    target.append(["META DE REGISTROS"])
    target.append(["COD.", "Entidade", "JAN", "FEV"])
    target.append([7501, "Goiânia", 20, 25])
    actual = workbook.create_sheet("Faturamento")
    actual.append(list(range(1, 15)))
    actual.append(["CONSULTAS REALIZADAS"])
    actual.append(["COD.", "Entidade", "JAN", "FEV"])
    actual.append([7501, "Goiânia", 80, 90])
    actual.append(list(range(1, 15)))
    actual.append(["REGISTROS REALIZADOS"])
    actual.append(["COD.", "Entidade", "JAN", "FEV"])
    actual.append([7501, "Goiânia", 15, 18])
    workbook.save(path)

    result = HistoricalWorkbookParser().parse(path)

    assert [
        (row.line, row.code, row.month, row.indicator, row.target, row.actual)
        for row in result.data
    ] == [
        (4, 7501, 1, "CONSULTAS", Decimal("100.0000"), Decimal("80.0000")),
        (4, 7501, 2, "CONSULTAS", Decimal("110.0000"), Decimal("90.0000")),
        (9, 7501, 1, "REGISTROS", Decimal("20.0000"), Decimal("15.0000")),
        (9, 7501, 2, "REGISTROS", Decimal("25.0000"), Decimal("18.0000")),
    ]
    assert all(row.code != 1 for row in result.data)
    assert not any("REGISTROS só serão importados" in item for item in result.warnings)


def test_parser_supports_official_2025_layout_by_structure_and_internal_year(tmp_path):
    path = tmp_path / "Meta x Realizado - Oficial.xlsm"
    _official_multiyear_workbook(
        path, actual_sheet="Desempenho", association_sheet="Mov. SPC",
        association_header_row=2, internal_year=2025,
    )

    result = HistoricalWorkbookParser().parse(path)

    assert result.can_import
    assert result.metadata.year == 2025
    assert {(row.indicator, row.month) for row in result.data if isinstance(row, TargetImportData)} == {
        ("CONSULTAS", 1), ("CONSULTAS", 2),
        ("REGISTROS", 1), ("REGISTROS", 2),
    }
    association = next(row for row in result.data if isinstance(row, AssociationImportData))
    assert (association.line, association.month, association.capture) == (
        4, 1, Decimal("10.0000")
    )


def test_parser_preserves_official_2026_layout_and_unaccented_headers(tmp_path):
    path = tmp_path / "Meta x Realizado - Oficial 2026.xlsm"
    _official_multiyear_workbook(path, capture_header="CAPTACAO")

    result = HistoricalWorkbookParser().parse(path)

    assert result.can_import
    assert result.metadata.year == 2026
    association = next(row for row in result.data if isinstance(row, AssociationImportData))
    assert (association.line, association.month, association.execution) == (
        3, 1, Decimal("100.0000")
    )


def test_parser_rejects_2025_summary_associations_without_raw_signature(tmp_path):
    path = tmp_path / "Meta x Realizado 2025.xlsx"
    _official_multiyear_workbook(path, actual_sheet="Desempenho")
    # Replace only the raw association layout with the known summary shape.
    source = load_workbook(path)
    sheet = source["Associações"]
    source.remove(sheet)
    summary = source.create_sheet("Associações")
    summary.append(["ASSOCIADOS", "TRIMESTRE"])
    summary.append(["COD.", "ENTIDADE", "SITUAÇÃO 2024", "JAN", "CAP.", "EXC."])
    summary.append([7501, "Goiânia", 90, 100, 10, 5])
    source.save(path)
    source.close()

    result = HistoricalWorkbookParser().parse(path)

    assert result.can_import
    assert not any(isinstance(row, AssociationImportData) for row in result.data)


def test_parser_reports_conflicting_year_evidence(tmp_path):
    path = tmp_path / "Meta x Realizado 2026.xlsx"
    _official_multiyear_workbook(path, internal_year=2025)

    result = HistoricalWorkbookParser().parse(path)

    assert not result.can_import
    assert "conflitantes" in result.errors[0]
    assert "2025" in result.errors[0] and "2026" in result.errors[0]


def test_parser_reports_missing_year_without_silent_2026_fallback(tmp_path):
    path = tmp_path / "Meta x Realizado - Oficial.xlsx"
    _official_multiyear_workbook(path)

    result = HistoricalWorkbookParser().parse(path)

    assert not result.can_import
    assert result.metadata.year is None
    assert "Ano das Metas não identificado" in result.errors[0]
