from decimal import Decimal
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt

from app.gui.pages.boe import BoePage
from app.gui.pages.dashboard import DashboardPage
from app.gui.pages.metas import MetasPage
from app.models.boe_entity_total import BOEEntityTotal
from app.models.entity import Entity
from app.models.target_entry import TargetEntry
from app.services.boe_service import BOEOperationalEntityOption
from app.services.remote_services import RemoteBOEService, RemoteDashboardService
from app.widgets.entity_multi_select import EntityMultiSelectCombo
from tests.boe_helpers import add_boe_import
from tests.test_boe_operational_filters import _api_context, _headers
from tests.test_dashboard_service import make_services


def test_shared_entity_combo_supports_all_multiple_empty_and_reload(qtbot):
    combo = EntityMultiSelectCombo()
    qtbot.addWidget(combo)
    options = (("7501 — Primeira", 1), ("7502 — Segunda", 2))
    combo.set_options(options, None)

    assert combo.selected_values() is None
    assert combo.selection_text() == "Todas as Entidades"

    combo.set_selected_values((1, 2))
    combo.set_options(options)
    assert combo.selected_values() is None

    combo.set_selected_values((2,))
    combo.set_options(options)
    assert combo.selected_values() == (2,)
    assert combo.selection_text() == "7502 — Segunda"

    combo.set_selected_values(())
    assert combo.selected_values() == ()
    assert combo.selection_text() == "Nenhuma Entidade"

    combo.set_options((), None)
    assert combo.selected_values() == ()
    assert combo.selection_text() == "Nenhuma Entidade disponível"


@pytest.mark.parametrize("click_area", ("left", "center", "text", "right"))
def test_shared_entity_combo_opens_popup_from_entire_field(qtbot, click_area):
    combo = EntityMultiSelectCombo()
    combo.resize(320, 36)
    combo.set_options((("7501 — Primeira", 1), ("7502 — Segunda", 2)))
    qtbot.addWidget(combo)
    combo.show()

    if click_area == "right":
        target = combo
        point = QPoint(combo.width() - 5, combo.height() // 2)
    else:
        target = combo.lineEdit()
        positions = {
            "left": 2,
            "text": min(35, combo.lineEdit().width() - 2),
            "center": combo.lineEdit().width() // 2,
        }
        point = QPoint(positions[click_area], combo.lineEdit().height() // 2)

    qtbot.mouseClick(target, Qt.MouseButton.LeftButton, pos=point)
    qtbot.waitUntil(lambda: combo.view().isVisible(), timeout=1000)
    qtbot.wait(50)

    assert combo.view().isVisible()
    combo.hidePopup()


def test_popup_checkbox_selection_stays_open_and_preserves_multiple(qtbot):
    combo = EntityMultiSelectCombo()
    combo.resize(320, 36)
    combo.set_options(
        (("7501 — Primeira", 1), ("7502 — Segunda", 2), ("7503 — Terceira", 3)),
        (),
    )
    qtbot.addWidget(combo)
    combo.show()
    qtbot.mouseClick(
        combo.lineEdit(),
        Qt.MouseButton.LeftButton,
        pos=QPoint(combo.lineEdit().width() // 2, combo.lineEdit().height() // 2),
    )
    qtbot.waitUntil(lambda: combo.view().isVisible(), timeout=1000)

    for row in (1, 2):
        index = combo.model().index(row, 0)
        point = combo.view().visualRect(index).center()
        qtbot.mouseClick(
            combo.view().viewport(), Qt.MouseButton.LeftButton, pos=point
        )
        assert combo.view().isVisible()

    assert combo.selected_values() == (1, 2)
    assert combo.selection_text() == "2 Entidades selecionadas"
    combo.hidePopup()


def test_all_five_entity_filters_use_shared_component(qtbot):
    dashboard = DashboardPage()
    boe = BoePage()
    targets = MetasPage()
    for page in (dashboard, boe, targets):
        qtbot.addWidget(page)

    assert isinstance(dashboard.boe_entity_filter, EntityMultiSelectCombo)
    assert isinstance(dashboard.target_entity_filter, EntityMultiSelectCombo)
    assert isinstance(boe.entity_filter, EntityMultiSelectCombo)
    assert isinstance(targets.entity_filter, EntityMultiSelectCombo)
    assert isinstance(targets.ranking_entity, EntityMultiSelectCombo)


def test_dashboard_filters_emit_typed_plural_contracts(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)
    page.set_dashboard_entity_options({
        "boe": [
            {"id": 1, "source_code": None, "code": 7501, "name": "CDL"},
            {"id": 2, "source_code": None, "code": 7502, "name": "Outra"},
            {"id": None, "source_code": 7600, "code": 7600, "name": "FCDL"},
        ],
        "targets": [
            {"id": 1, "code": 7501, "name": "CDL"},
            {"id": 2, "code": 7502, "name": "Outra"},
            {"id": 3, "code": 7503, "name": "Terceira"},
        ],
    })
    page.boe_entity_filter.set_selected_values((
        ("master_entity", 1), ("boe_source", 7600),
    ))
    page.target_entity_filter.set_selected_values((
        ("master_entity", 1), ("master_entity", 2),
    ))

    filters = page.selected_dashboard_filters()

    assert filters["boe_entity_id"] is None
    assert filters["boe_source_code"] is None
    assert filters["boe_entity_ids"] == (1,)
    assert filters["boe_source_codes"] == (7600,)
    assert filters["target_entity_id"] is None
    assert filters["target_entity_ids"] == (1, 2)


def test_boe_page_combines_master_entities_and_fcdl(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    page.set_import_periods((
        SimpleNamespace(periodo_ano=2026, periodo_mes=9, status="imported"),
    ))
    page.set_operational_entities((
        BOEOperationalEntityOption(1, None, "CDL", 7501),
        BOEOperationalEntityOption(2, None, "Outra", 7502),
        BOEOperationalEntityOption(None, 7600, "FCDL", 7600),
    ))
    page.entity_filter.set_selected_values((
        ("master_entity", 1), ("boe_source", 7600),
    ))

    assert page.operational_filters() == (
        2026, 1, 2026, 12, None, None, (1,), (7600,),
    )

    page.entity_filter.set_selected_values(())
    with pytest.raises(ValueError, match="ao menos uma"):
        page.operational_filters()


def test_boe_multiple_filter_is_union_without_duplicates_or_7500(db_session):
    dashboard, _, _, boe, _, _ = make_services(db_session)
    first = Entity(codigo_entidade=7501, nome="Primeira")
    second = Entity(codigo_entidade=7502, nome="Segunda")
    db_session.add_all((first, second))
    db_session.flush()
    imported = add_boe_import(db_session, year=2026, month=9)
    db_session.add_all((
        BOEEntityTotal(
            boe_import_id=imported.id, entity_id=first.id,
            codigo_entidade_origem=7501, nome_entidade_origem="Primeira",
            quantidade_consultas=10, valor_total=Decimal("10"),
        ),
        BOEEntityTotal(
            boe_import_id=imported.id, entity_id=second.id,
            codigo_entidade_origem=7502, nome_entidade_origem="Segunda",
            quantidade_consultas=20, valor_total=Decimal("20"),
        ),
        BOEEntityTotal(
            boe_import_id=imported.id, entity_id=None,
            codigo_entidade_origem=7600, nome_entidade_origem="FCDL",
            quantidade_consultas=5, valor_total=Decimal("5"),
        ),
        BOEEntityTotal(
            boe_import_id=imported.id, entity_id=None,
            codigo_entidade_origem=7500, nome_entidade_origem="TOTAL",
            quantidade_consultas=999, valor_total=Decimal("999"),
        ),
    ))
    db_session.commit()

    result = boe.query_operations(
        2026, 9, 2026, 9,
        entity_ids=[first.id, first.id, second.id],
        source_codes=[7600, 7600],
    )
    dashboard_result = dashboard.get_boe_dashboard(
        2026, start_month=9, end_month=9,
        entity_ids=[first.id, second.id, first.id],
        source_codes=[7600, 7600],
    )

    assert result.total_queries == 35
    assert len(result.rows) == 3
    assert dashboard_result["queries"] == 35
    assert {row["code"] for row in dashboard_result["entities"]} == {
        7501, 7502, 7600,
    }


def test_target_dashboard_multiple_filter_respects_region(db_session):
    dashboard, *_ = make_services(db_session)
    north_a = Entity(codigo_entidade=7501, nome="Norte A", regiao="NORTE")
    north_b = Entity(codigo_entidade=7502, nome="Norte B", regiao="NORTE")
    south = Entity(codigo_entidade=7503, nome="Sul", regiao="SUL")
    db_session.add_all((north_a, north_b, south))
    db_session.flush()
    for entity, value in ((north_a, 10), (north_b, 20), (south, 100)):
        db_session.add(TargetEntry(
            entity_id=entity.id, periodo_ano=2026, periodo_mes=1,
            indicador="CONSULTAS", valor_meta=value, valor_realizado=value,
        ))
    db_session.commit()

    result = dashboard.get_targets_dashboard(
        2026,
        indicator="CONSULTAS",
        start_month=1,
        end_month=1,
        region="NORTE",
        entity_ids=[north_a.id, north_b.id, north_a.id, south.id],
    )

    assert result["total"]["target"] == Decimal("30")
    with pytest.raises(ValueError, match="incompatíveis"):
        dashboard.get_targets_dashboard(
            2026, north_a.id, entity_ids=[north_b.id]
        )


def test_remote_services_serialize_repeated_plural_parameters():
    class API:
        def __init__(self):
            self.paths = []

        def get(self, path):
            self.paths.append(path)
            return {
                "rows": [], "total_queries": 0,
                "unit_value": 0, "total_value": 0,
            }

    boe_api = API()
    RemoteBOEService(boe_api).query_operations(
        2026, 1, 2026, 12,
        entity_ids=(1, 2), source_codes=(7600,),
    )
    assert "entity_ids=1&entity_ids=2" in boe_api.paths[-1]
    assert "source_codes=7600" in boe_api.paths[-1]

    dashboard_api = API()
    RemoteDashboardService(dashboard_api, {"boe", "targets"}).get_dashboard_data(
        2026, 1,
        boe_entity_ids=(1, 2), boe_source_codes=(7600,),
        target_entity_ids=(1, 2),
    )
    assert any("entity_ids=1&entity_ids=2" in path for path in dashboard_api.paths)
    assert any("source_codes=7600" in path for path in dashboard_api.paths)


def test_dashboard_api_accepts_plural_and_preserves_legacy_contract(tmp_path):
    from fastapi.testclient import TestClient

    app, entity_id = _api_context(tmp_path)
    with TestClient(app) as client:
        headers = _headers(client)
        multiple = client.get(
            "/api/v1/dashboard/boe"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9"
            f"&entity_ids={entity_id}&entity_ids={entity_id}"
            "&source_codes=7600",
            headers=headers,
        )
        legacy = client.get(
            "/api/v1/dashboard/boe"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9"
            "&source_code=7600",
            headers=headers,
        )
        incompatible = client.get(
            "/api/v1/dashboard/boe"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9"
            f"&entity_id={entity_id}&entity_ids={entity_id}",
            headers=headers,
        )
        empty = client.get(
            "/api/v1/dashboard/boe"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9"
            "&entity_ids=",
            headers=headers,
        )

    assert multiple.status_code == 200
    assert multiple.json()["queries"] == 15
    assert legacy.status_code == 200
    assert legacy.json()["queries"] == 5
    assert incompatible.status_code == 422
    assert empty.status_code == 422
    app.state.engine.dispose()


def test_ranking_filter_supports_multiple_entities(qtbot):
    page = MetasPage()
    qtbot.addWidget(page)

    def row(entity_id):
        return SimpleNamespace(
            entity_id=entity_id, entity_code=7500 + entity_id,
            entity_name=f"Entidade {entity_id}", strategy_year=2026,
            classified=True, technical_tie=False, position=entity_id,
            target_total=Decimal("10"), actual_total=Decimal("10"),
            achievement=Decimal("100"), captures=0, cancellations=0,
            billing_points=5, capture_points=2, cancellation_points=1,
            score=8, award=None, category_results=(),
            meta_queries=Decimal("5"), actual_queries=Decimal("5"),
            meta_registrations=Decimal("5"), actual_registrations=Decimal("5"),
        )

    rows = [row(1), row(2), row(3)]
    page.show_ranking(rows, [])
    page.ranking_entity.set_selected_values((1, 3))
    page.show_ranking(rows, [])

    assert page.ranking_table.rowCount() == 2
    assert page.ranking_entity.selection_text() == "2 Entidades selecionadas"
