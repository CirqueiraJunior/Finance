from decimal import Decimal

from fastapi.testclient import TestClient
import pytest

from app.gui.controllers.dashboard_controller import DashboardController
from app.gui.pages.dashboard import DashboardPage
from app.models.boe_entity_total import BOEEntityTotal
from app.models.entity import Entity
from app.services.remote_services import RemoteDashboardService
from finance_server.app_factory import create_app
from finance_server.config import ServerSettings
from finance_server.models import User, UserRole
from finance_server.security import hash_password
from tests.boe_helpers import add_boe_import
from tests.test_dashboard_service import make_services


PASSWORD = "Strong!Pass123"


def test_dashboard_loads_entity_options_without_loading_panels(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    class Service:
        def __init__(self):
            self.entity_calls = []
            self.dashboard_calls = 0

        def get_available_years(self):
            return {
                "financial_years": [2026],
                "boe_years": [2026],
                "target_years": [2026],
            }

        def get_dashboard_entity_options(self, areas=None, region=None):
            self.entity_calls.append((set(areas), region))
            return {
                "boe": [
                    {"id": 1, "source_code": None, "code": 7501,
                     "name": "CDL Goiânia"},
                    {"id": None, "source_code": 7600, "code": 7600,
                     "name": "FCDL"},
                ],
                "targets": [
                    {"id": 1, "code": 7501, "name": "CDL Goiânia"}
                ],
            }

        def get_dashboard_data(self, *_args, **_kwargs):
            self.dashboard_calls += 1
            return {}

    service = Service()
    controller = DashboardController(page, service)
    qtbot.waitUntil(
        lambda: (
            controller._entities_thread is None
            and controller._years_thread is None
        ),
        timeout=5000,
    )

    assert service.dashboard_calls == 0
    assert service.entity_calls == [({"boe", "targets"}, None)]
    assert page.boe_entity_filter.count() == 3
    assert page.boe_entity_filter.itemData(2) == ("boe_source", 7600)
    assert page.target_entity_filter.count() == 2


def test_dashboard_entity_options_preserve_valid_selection_and_fcdl_contract(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)
    options = {
        "boe": [
            {"id": 7, "source_code": None, "code": 7507, "name": "CDL 7"},
            {"id": None, "source_code": 7600, "code": 7600, "name": "FCDL"},
        ],
        "targets": [
            {"id": 7, "code": 7507, "name": "CDL 7"},
            {"id": 8, "code": 7508, "name": "CDL 8"},
        ],
    }
    page.set_dashboard_entity_options(options)
    page.boe_entity_filter.set_selected_values((("boe_source", 7600),))
    page.target_entity_filter.set_selected_values((("master_entity", 8),))

    page.set_dashboard_entity_options(options)

    assert page.boe_entity_filter.selected_values() == (("boe_source", 7600),)
    assert page.target_entity_filter.selected_values() == (
        ("master_entity", 8),
    )
    filters = page.selected_dashboard_filters()
    assert filters["boe_entity_id"] is None
    assert filters["boe_source_code"] == 7600
    assert filters["target_entity_id"] == 8


def test_dashboard_entity_error_does_not_clear_existing_options(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    class Service:
        fail = False

        def get_available_years(self):
            return {
                "financial_years": [2026], "boe_years": [2026],
                "target_years": [2026],
            }

        def get_dashboard_entity_options(self, areas=None, region=None):
            if self.fail:
                raise RuntimeError("indisponível")
            return {
                "boe": [
                    {"id": 1, "source_code": None, "code": 7501,
                     "name": "CDL"}
                ],
                "targets": [],
            }

    service = Service()
    controller = DashboardController(page, service)
    qtbot.waitUntil(lambda: controller._entities_thread is None, timeout=5000)
    assert page.boe_entity_filter.count() == 2

    service.fail = True
    controller.refresh_entity_options({"boe"})
    qtbot.waitUntil(lambda: controller._entities_thread is None, timeout=5000)

    assert page.boe_entity_filter.count() == 2
    assert "indisponível" in page.status.text()


def test_dashboard_region_reloads_only_target_options(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    class Service:
        def __init__(self):
            self.calls = []

        def get_available_years(self):
            return {
                "financial_years": [2026], "boe_years": [2026],
                "target_years": [2026],
            }

        def get_dashboard_entity_options(self, areas=None, region=None):
            self.calls.append((set(areas), region))
            return {area: [] for area in areas}

    service = Service()
    controller = DashboardController(page, service)
    qtbot.waitUntil(lambda: controller._entities_thread is None, timeout=5000)
    page.target_region_filter.setCurrentIndex(
        page.target_region_filter.findData("NORTE")
    )
    qtbot.waitUntil(
        lambda: len(service.calls) == 2 and controller._entities_thread is None,
        timeout=5000,
    )

    assert service.calls[-1] == ({"targets"}, "NORTE")


def test_remote_dashboard_entity_options_respect_allowed_areas():
    class API:
        def __init__(self):
            self.paths = []

        def get(self, path):
            self.paths.append(path)
            return []

    api = API()
    result = RemoteDashboardService(api, {"boe"}).get_dashboard_entity_options(
        areas={"boe", "targets"}, region="NORTE"
    )

    assert result == {"boe": []}
    assert api.paths == ["/api/v1/dashboard/boe/entities"]


def test_remote_dashboard_uses_source_code_for_fcdl_selection():
    class API:
        def __init__(self):
            self.paths = []

        def get(self, path):
            self.paths.append(path)
            return {}

    api = API()
    RemoteDashboardService(api, {"boe"}).get_dashboard_data(
        2026,
        9,
        areas={"boe"},
        boe_start_year=2026,
        boe_start_month=9,
        boe_end_year=2026,
        boe_end_month=9,
        boe_source_code=7600,
    )

    assert len(api.paths) == 1
    assert "source_code=7600" in api.paths[0]
    assert "entity_id=" not in api.paths[0]


def test_dashboard_metadata_excludes_7500_and_keeps_fcdl_source_filter(db_session):
    dashboard, *_ = make_services(db_session)
    entity = Entity(codigo_entidade=7501, nome="CDL Goiânia", regiao="CENTRO")
    other = Entity(codigo_entidade=7502, nome="CDL Sul", regiao="SUL")
    db_session.add_all((entity, other))
    db_session.flush()
    imported = add_boe_import(db_session, year=2026, month=9)
    db_session.add_all([
        BOEEntityTotal(
            boe_import_id=imported.id, entity_id=entity.id,
            codigo_entidade_origem=7501, nome_entidade_origem=entity.nome,
            quantidade_consultas=10, valor_total=Decimal("10"),
        ),
        BOEEntityTotal(
            boe_import_id=imported.id, entity_id=None,
            codigo_entidade_origem=7600, nome_entidade_origem="FCDL",
            quantidade_consultas=5, valor_total=Decimal("5"),
        ),
        BOEEntityTotal(
            boe_import_id=imported.id, entity_id=None,
            codigo_entidade_origem=7500, nome_entidade_origem="TOTAL GERAL",
            quantidade_consultas=999, valor_total=Decimal("999"),
        ),
    ])
    db_session.commit()

    options = dashboard.get_dashboard_entity_options(
        {"boe", "targets"}, region="CENTRO"
    )
    filtered = dashboard.get_boe_dashboard(
        2026, entity_id=entity.id, start_month=9, end_month=9
    )
    all_entities = dashboard.get_boe_dashboard(
        2026, start_month=9, end_month=9
    )
    fcdl = dashboard.get_boe_dashboard(
        2026, source_code=7600, start_month=9, end_month=9
    )

    assert [row["code"] for row in options["boe"]] == [7501, 7600]
    assert options["boe"][1]["id"] is None
    assert options["boe"][1]["source_code"] == 7600
    assert [row["code"] for row in options["targets"]] == [7501]
    assert [row["code"] for row in filtered["filters"]["entities"]] == [
        7501, 7600
    ]
    assert fcdl["queries"] == 5
    assert [row["code"] for row in fcdl["entities"]] == [7600]
    assert all_entities["queries"] == 15
    with pytest.raises(ValueError, match="apenas entity_id ou source_code"):
        dashboard.get_boe_dashboard(
            2026, entity_id=entity.id, source_code=7600
        )
    with pytest.raises(ValueError, match="não autorizado"):
        dashboard.get_boe_dashboard(2026, source_code=7500)


def test_dashboard_metadata_endpoints_enforce_area_permissions(tmp_path):
    settings = ServerSettings(
        f"sqlite:///{(tmp_path / 'dashboard-metadata.db').as_posix()}",
        "s" * 64,
    )
    app = create_app(settings, create_schema=True)
    with app.state.session_factory() as session:
        for username, role in (
            ("finance", UserRole.FINANCE_OPERATOR.value),
            ("boe", UserRole.BOE_OPERATOR.value),
            ("consulta", UserRole.READ_ONLY.value),
        ):
            session.add(User(
                nome=username.title(), email=f"{username}@test.local",
                username=username, password_hash=hash_password(PASSWORD),
                perfil=role, ativo=True,
            ))
        session.commit()

    def headers(client, username):
        response = client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": PASSWORD},
        )
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    with TestClient(app) as client:
        finance = headers(client, "finance")
        boe = headers(client, "boe")
        consulta = headers(client, "consulta")
        assert client.get(
            "/api/v1/dashboard/boe/entities", headers=finance
        ).status_code == 403
        assert client.get(
            "/api/v1/dashboard/boe/entities", headers=boe
        ).status_code == 200
        assert client.get(
            "/api/v1/dashboard/targets/entities", headers=boe
        ).status_code == 403
        assert client.get(
            "/api/v1/dashboard/targets/entities?region=NORTE",
            headers=consulta,
        ).status_code == 200
    app.state.engine.dispose()
