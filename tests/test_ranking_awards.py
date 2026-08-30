from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.gui.pages.metas import MetasPage
from app.importers.historical_importer import HistoricalWorkbookImporter
from app.models.association_entry import AssociationEntry
from app.models.cashflow_entry import CashflowEntry
from app.models.entity import Entity
from app.models.target_entry import TargetEntry, TargetIndicator
from app.repositories.association_repository import AssociationRepository
from app.repositories.target_repository import TargetRepository
from app.services.award_service import AwardService
from app.services.ranking_service import QUARTER_MONTHS, RankingService
from app.importers.historical_importer import HistoricalPreview
from app.services.historical_import_service import HistoricalImportService


@pytest.mark.parametrize("percentage,expected", [
    ("99.99", 0), ("100", 5), ("109.99", 5), ("110", 6),
    ("149.99", 6), ("150", 7),
])
def test_official_billing_boundaries(percentage, expected):
    assert RankingService.billing_points(Decimal(percentage)) == expected


@pytest.mark.parametrize("captures,expected", [
    (0, 0), (1, 2), (7, 2), (8, 3), (15, 3), (16, 4),
])
def test_capture_boundaries(captures, expected):
    assert RankingService.capture_points(Decimal(captures)) == expected


def test_cancellation_awards_and_quarter_months():
    assert RankingService.cancellation_points(Decimal("0")) == 1
    assert RankingService.cancellation_points(Decimal("1")) == 0
    assert [AwardService.value_for_position(position) for position in range(1, 5)] == [
        Decimal("3000.00"), Decimal("2000.00"), Decimal("1000.00"), None,
    ]
    assert QUARTER_MONTHS == {
        1: (1, 2, 3), 2: (4, 5, 6), 3: (7, 8, 9), 4: (10, 11, 12),
    }


def add_entity_result(session, code, target, actual, captures=0, cancellations=0,
                      quarter=1):
    entity = Entity(codigo_entidade=code, nome=f"Entidade {code}")
    session.add(entity)
    session.flush()
    month = QUARTER_MONTHS[quarter][0]
    for indicator in (TargetIndicator.QUERIES.value, TargetIndicator.REGISTRATIONS.value):
        session.add(TargetEntry(
            entity_id=entity.id, periodo_ano=2026, periodo_mes=month,
            indicador=indicator, valor_meta=Decimal(target) / 2,
            valor_realizado=Decimal(actual) / 2,
        ))
    session.add(AssociationEntry(
        entity_id=entity.id, periodo_ano=2026, periodo_mes=month,
        valor_captacao=Decimal(captures), valor_execucao=0,
        valor_cancelamento=Decimal(cancellations),
    ))
    session.flush()
    return entity


def ranking_service(session):
    return RankingService(TargetRepository(session), AssociationRepository(session))


def test_exactly_100_is_classified_99_99_is_disqualified_and_no_expense(db_session):
    add_entity_result(db_session, 7501, "100", "100", 1, 0)
    add_entity_result(db_session, 7502, "100", "99.99", 16, 0)
    before = db_session.scalar(select(func.count()).select_from(CashflowEntry))
    rows = ranking_service(db_session).quarterly(2026, 1)
    assert rows[0].classified and rows[0].billing_points == 5
    assert rows[0].award == Decimal("3000.00")
    assert not rows[1].classified and rows[1].position is None
    assert db_session.scalar(select(func.count()).select_from(CashflowEntry)) == before


def test_ranking_score_official_tiebreak_and_technical_tie(db_session):
    add_entity_result(db_session, 7501, "100", "120", 8, 1)
    add_entity_result(db_session, 7502, "100", "130", 8, 1)
    add_entity_result(db_session, 7503, "100", "130", 8, 1)
    rows = ranking_service(db_session).quarterly(2026, 1)
    assert [row.entity_code for row in rows] == [7502, 7503, 7501]
    assert rows[0].position == rows[1].position == 1
    assert rows[0].technical_tie and rows[0].award is None
    assert rows[2].position == 3 and rows[2].award == Decimal("1000.00")


def test_ranking_applies_all_operational_tiebreakers_before_awards(db_session):
    # Mesmo Score (9) e atingimento: maior Captação vence primeiro.
    add_entity_result(db_session, 7510, "100", "120", 8, 1)
    add_entity_result(db_session, 7511, "100", "120", 12, 1)
    # Mesmo Score (8), atingimento e Captação: menor Cancelamento vence.
    add_entity_result(db_session, 7512, "100", "105", 7, 3)
    add_entity_result(db_session, 7513, "100", "105", 7, 1)
    rows = ranking_service(db_session).quarterly(2026, 1)
    assert [row.entity_code for row in rows] == [7511, 7510, 7513, 7512]
    assert [row.position for row in rows] == [1, 2, 3, 4]
    assert [row.award for row in rows] == [
        Decimal("3000.00"), Decimal("2000.00"), Decimal("1000.00"), None,
    ]
    assert not any(row.technical_tie for row in rows)


def test_higher_score_precedes_higher_achievement(db_session):
    add_entity_result(db_session, 7520, "100", "150", 0, 1)   # score 7
    add_entity_result(db_session, 7521, "100", "110", 16, 0)  # score 11
    rows = ranking_service(db_session).quarterly(2026, 1)
    assert [row.entity_code for row in rows] == [7521, 7520]


def test_higher_achievement_breaks_equal_score(db_session):
    add_entity_result(db_session, 7530, "100", "120", 8, 1)   # score 9
    add_entity_result(db_session, 7531, "100", "140", 8, 1)   # score 9
    rows = ranking_service(db_session).quarterly(2026, 1)
    assert [row.entity_code for row in rows] == [7531, 7530]


def test_annual_view_is_informative_and_does_not_sum_scores(db_session):
    entity = add_entity_result(db_session, 7501, "100", "150", 16, 0, 1)
    for quarter in (2, 3, 4):
        month = QUARTER_MONTHS[quarter][0]
        for indicator in (TargetIndicator.QUERIES.value, TargetIndicator.REGISTRATIONS.value):
            db_session.add(TargetEntry(
                entity_id=entity.id, periodo_ano=2026, periodo_mes=month,
                indicador=indicator, valor_meta=50, valor_realizado=50,
            ))
        db_session.add(AssociationEntry(
            entity_id=entity.id, periodo_ano=2026, periodo_mes=month,
            valor_captacao=0, valor_execucao=0, valor_cancelamento=0,
        ))
    db_session.flush()
    annual = ranking_service(db_session).annual(2026)[0]
    assert annual.positions == (1, 1, 1, 1)
    assert annual.classified_quarters == 4
    assert annual.award_count == 4
    assert annual.award_total == Decimal("12000.00")
    assert not hasattr(annual, "score")


def test_ranking_gui_has_official_views(qtbot, db_session):
    add_entity_result(db_session, 7501, "100", "100", 1, 0)
    page = MetasPage()
    qtbot.addWidget(page)
    rows = ranking_service(db_session).quarterly(2026, 1)
    page.show_ranking(rows, ranking_service(db_session).annual(2026))
    assert page.tabs.tabText(1) == "Ranking e Premiação"
    assert page.ranking_table.columnCount() == 14
    assert "Entidade 7501" in page.champions.text()
    assert page.annual_table.rowCount() == 1


def test_association_preview_maps_cancellation_without_reusing_capture(tmp_path):
    from openpyxl import Workbook
    path = tmp_path / "associations-2026.xlsx"
    book = Workbook()
    sheet = book.active
    sheet.title = "Associações"
    sheet.append(["CÓD", "ENTIDADES", "JANEIRO", None, None, None])
    sheet.append([None, None, "CANC.", "CAPTAÇÃO", "SUSPENSO", "TOTAL ASSC."])
    sheet.append([7501, "Goiânia", 3, 8, 1, 100])
    book.save(path)
    row = HistoricalWorkbookImporter().parse_association(path).rows[0]
    assert row["cancellation"] == Decimal("3.0000")
    assert row["capture"] == Decimal("8.0000")


def test_existing_association_is_updated_for_cancellation_not_discarded(db_session, tmp_path):
    entity = Entity(codigo_entidade=7501, nome="Goiânia")
    db_session.add(entity)
    db_session.flush()
    db_session.add(AssociationEntry(
        entity_id=entity.id, periodo_ano=2026, periodo_mes=1,
        valor_captacao=8, valor_execucao=100, valor_cancelamento=0,
    ))
    db_session.commit()

    class BackupStub:
        def create_import_backup(self):
            path = tmp_path / "backup.db"
            path.write_bytes(b"backup")
            return path

    service = HistoricalImportService(
        db_session, HistoricalWorkbookImporter(), None, None, BackupStub(), None
    )
    preview = HistoricalPreview(tmp_path / "source.xlsx", "ASSOCIACAO", 2026, rows=[{
        "line": 3, "entity_id": entity.id, "year": 2026, "month": 1,
        "capture": Decimal("8.0000"), "execution": Decimal("100.0000"),
        "cancellation": Decimal("3.0000"),
    }])
    service._mark_duplicates(preview)
    assert preview.rows[0]["update"] is True
    assert preview.duplicates == 0
    service.import_preview(preview)
    persisted = db_session.scalar(select(AssociationEntry))
    assert persisted.valor_cancelamento == Decimal("3.0000")
    assert db_session.scalar(select(func.count()).select_from(CashflowEntry)) == 0
