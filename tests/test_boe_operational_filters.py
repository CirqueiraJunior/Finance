from decimal import Decimal

from fastapi.testclient import TestClient

from app.gui.pages.boe import BoePage
from app.models.boe_entity_total import BOEEntityTotal
from app.models.entity import Entity
from app.services.boe_service import BOEOperationalEntityOption
from app.services.remote_services import RemoteBOEService
from finance_server.app_factory import create_app
from finance_server.config import ServerSettings
from finance_server.models import User, UserRole
from finance_server.security import hash_password
from tests.boe_helpers import add_boe_import


PASSWORD = "Strong!Pass123"


def _api_context(tmp_path):
    settings = ServerSettings(
        f"sqlite:///{(tmp_path / 'boe-operational.db').as_posix()}",
        "s" * 64,
    )
    app = create_app(settings, create_schema=True)
    with app.state.session_factory() as session:
        user = User(
            nome="Administrador",
            email="admin@finance.test",
            username="admin",
            password_hash=hash_password(PASSWORD),
            perfil=UserRole.ADMINISTRATOR.value,
            ativo=True,
        )
        entity = Entity(
            codigo_entidade=7501,
            nome="CDL GOIANIA/GO",
            nome_oficial="CDL Goiânia",
        )
        session.add_all([user, entity])
        session.commit()
        imported = add_boe_import(
            session,
            year=2026,
            month=9,
            file_hash="f" * 64,
        )
        session.add_all([
            BOEEntityTotal(
                boe_import_id=imported.id,
                entity_id=entity.id,
                codigo_entidade_origem=7501,
                nome_entidade_origem=entity.nome,
                quantidade_consultas=10,
                valor_total=Decimal("10.0000"),
            ),
            BOEEntityTotal(
                boe_import_id=imported.id,
                entity_id=None,
                codigo_entidade_origem=7600,
                nome_entidade_origem="FCDL",
                quantidade_consultas=5,
                valor_total=Decimal("5.0000"),
            ),
            BOEEntityTotal(
                boe_import_id=imported.id,
                entity_id=None,
                codigo_entidade_origem=7500,
                nome_entidade_origem="TOTAL GERAL",
                quantidade_consultas=999,
                valor_total=Decimal("999.0000"),
            ),
        ])
        session.commit()
        entity_id = entity.id
    return app, entity_id


def _headers(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"identifier": "admin", "password": PASSWORD},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_operational_api_filters_fcdl_and_rejects_ambiguous_parameters(
    tmp_path,
):
    app, entity_id = _api_context(tmp_path)
    with TestClient(app) as client:
        headers = _headers(client)
        options = client.get(
            "/api/v1/boe/operations/entities",
            headers=headers,
        )
        all_entities = client.get(
            "/api/v1/boe/operations"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9",
            headers=headers,
        )
        fcdl = client.get(
            "/api/v1/boe/operations"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9"
            "&source_code=7600",
            headers=headers,
        )
        master = client.get(
            "/api/v1/boe/operations"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9"
            f"&entity_id={entity_id}",
            headers=headers,
        )
        ambiguous = client.get(
            "/api/v1/boe/operations"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9"
            f"&entity_id={entity_id}&source_code=7600",
            headers=headers,
        )
        consolidated = client.get(
            "/api/v1/boe/operations"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9"
            "&source_code=7500",
            headers=headers,
        )
        unknown = client.get(
            "/api/v1/boe/operations"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9"
            "&source_code=9999",
            headers=headers,
        )
        multiple = client.get(
            "/api/v1/boe/operations"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9"
            f"&entity_ids={entity_id}&entity_ids={entity_id}"
            "&source_codes=7600&source_codes=7600",
            headers=headers,
        )
        mixed_contracts = client.get(
            "/api/v1/boe/operations"
            "?start_year=2026&start_month=9&end_year=2026&end_month=9"
            f"&entity_id={entity_id}&entity_ids={entity_id}",
            headers=headers,
        )

    assert options.status_code == 200
    assert options.json() == [
        {"id": entity_id, "source_code": None, "name": "CDL Goiânia"},
        {"id": None, "source_code": 7600, "name": "FCDL"},
    ]
    assert all_entities.status_code == 200
    assert all_entities.json()["total_queries"] == 15
    assert all_entities.json()["total_value"] == 15
    assert fcdl.status_code == 200
    assert len(fcdl.json()["rows"]) == 1
    assert fcdl.json()["rows"][0]["entity_name"] == "FCDL"
    assert fcdl.json()["total_queries"] == 5
    assert fcdl.json()["total_value"] == 5
    assert master.status_code == 200
    assert master.json()["total_queries"] == 10
    assert ambiguous.status_code == 422
    assert consolidated.status_code == 422
    assert unknown.status_code == 422
    assert multiple.status_code == 200
    assert multiple.json()["total_queries"] == 15
    assert len(multiple.json()["rows"]) == 2
    assert mixed_contracts.status_code == 422
    app.state.engine.dispose()


def test_boe_page_uses_distinct_selectors_for_all_master_and_fcdl(qtbot):
    page = BoePage()
    qtbot.addWidget(page)
    page.set_import_periods([
        type("Import", (), {
            "periodo_ano": 2026,
            "periodo_mes": 9,
            "status": "imported",
        })()
    ])
    page.set_operational_entities((
        BOEOperationalEntityOption(10, None, "CDL Goiânia"),
        BOEOperationalEntityOption(None, 7600, "FCDL"),
    ))

    page.entity_filter.set_selected_values(None)
    assert page.operational_filters() == (2026, 1, 2026, 12, None)

    page.entity_filter.set_selected_values((("master_entity", 10),))
    assert page.operational_filters() == (2026, 1, 2026, 12, 10)

    page.entity_filter.set_selected_values((("boe_source", 7600),))
    assert page.operational_filters() == (
        2026, 1, 2026, 12, None, 7600
    )


def test_remote_boe_service_transmits_source_code_without_entity_id():
    class API:
        def __init__(self):
            self.paths = []

        def get(self, path):
            self.paths.append(path)
            if path == "/api/v1/boe/operations/entities":
                return [
                    {"id": None, "source_code": 7600, "name": "FCDL"}
                ]
            return {
                "rows": [],
                "total_queries": 0,
                "unit_value": 0,
                "total_value": 0,
            }

    api = API()
    service = RemoteBOEService(api)

    assert service.list_operational_entities() == (
        BOEOperationalEntityOption(None, 7600, "FCDL"),
    )
    service.query_operations(2026, 1, 2026, 12, None, 7600)

    assert "source_code=7600" in api.paths[-1]
    assert "entity_id=" not in api.paths[-1]
