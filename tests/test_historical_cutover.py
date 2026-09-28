from decimal import Decimal
from types import SimpleNamespace

from app.importers.historical_importer import HistoricalPreview, HistoricalWorkbookImporter
from app.models.boe_import import BOEImport
from app.services.historical_import_service import HistoricalImportService


class CatalogStub:
    @staticmethod
    def list_entries():
        return [
            SimpleNamespace(
                descricao="Repasse historico",
                categoria="RECEITA_DIRETA",
                tipo="RECEITA",
                ativa=True,
            )
        ]


def make_preview(tmp_path, year=2026, month=1):
    return HistoricalPreview(
        tmp_path / "fluxo.xlsx",
        "FLUXO_CAIXA",
        2026,
        rows=[
            {
                "line": 3,
                "year": year,
                "month": month,
                "description": "Repasse historico",
                "notes": None,
                "category_label": "Receita Direta",
                "type_label": "Receita",
                "value": Decimal("12870.01"),
                "boe": False,
            }
        ],
    )


def make_service(db_session):
    return HistoricalImportService(
        db_session,
        HistoricalWorkbookImporter(),
        None,
        CatalogStub(),
        None,
        None,
    )


def test_historical_direct_is_allowed_before_cutover_without_previous_boe(
    db_session, tmp_path,
):
    preview = make_preview(tmp_path, year=2025, month=1)

    make_service(db_session)._validate_cashflow(preview)

    row = preview.rows[0]
    assert row["category"] == "RECEITA_DIRETA"
    assert row["type"] == "RECEITA"
    assert row.get("skip") is not True
    assert preview.warnings == [
        "Receita Direta de 01/2026 importada da base hist\u00f3rica "
        "por aus\u00eancia de BOE 12/2025."
    ]


def test_historical_january_2026_direct_is_skipped_with_december_boe(
    db_session, tmp_path,
):
    db_session.add(
        BOEImport(
            periodo_ano=2025,
            periodo_mes=12,
            nome_arquivo="BOE-12.25.xlsx",
            caminho_origem="fixture",
            hash_arquivo="9" * 64,
            quantidade_entidades=1,
            quantidade_inconsistencias=0,
            valor_total=Decimal("900"),
            status="imported",
        )
    )
    db_session.commit()

    preview = make_preview(tmp_path, year=2026, month=1)

    make_service(db_session)._validate_cashflow(preview)

    assert preview.rows[0]["skip"] is True
