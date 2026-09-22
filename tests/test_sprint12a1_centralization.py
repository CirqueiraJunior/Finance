from pathlib import Path

from fastapi.testclient import TestClient
from PySide6.QtCore import Qt
from sqlalchemy import select

from app.models.entity import Entity
from app.models.cashflow_entry import CashflowEntry
from app.models.budget_entry import BudgetEntry
from app.services.dashboard_service import DashboardService
from finance_server.app_factory import create_app
from finance_server.config import ServerSettings
from finance_server.models import User, UserRole
from finance_server.security import hash_password
from tests.boe_helpers import create_boe_workbook


PASSWORD = "Strong!Pass123"


def _context(tmp_path):
    settings = ServerSettings(f"sqlite:///{(tmp_path / 'server.db').as_posix()}", "s" * 64)
    app = create_app(settings, create_schema=True)
    with app.state.session_factory() as db:
        db.add_all([
            User(nome="Admin", email="admin@finance.test", username="admin",
                 password_hash=hash_password(PASSWORD), perfil=UserRole.ADMINISTRATOR.value, ativo=True),
            User(nome="Consulta", email="read@finance.test", username="read",
                 password_hash=hash_password(PASSWORD), perfil=UserRole.READ_ONLY.value, ativo=True),
            User(nome="Financeiro", email="finance@finance.test", username="finance",
                 password_hash=hash_password(PASSWORD), perfil=UserRole.FINANCE_OPERATOR.value, ativo=True),
            User(nome="BOE", email="boe@finance.test", username="boe",
                 password_hash=hash_password(PASSWORD), perfil=UserRole.BOE_OPERATOR.value, ativo=True),
            Entity(codigo_entidade=7501, nome="CDL GOIANIA/GO", nome_oficial="CDL GOIANIA/GO", ativa=True),
            Entity(codigo_entidade=7544, nome="CDL ANAPOLIS/GO", nome_oficial="CDL ANAPOLIS/GO", ativa=True),
        ])
        db.commit()
    return app


def _headers(client, username="admin"):
    pair = client.post("/api/v1/auth/login", json={"identifier": username, "password": PASSWORD}).json()
    return {"Authorization": f"Bearer {pair['access_token']}"}


def test_operational_endpoints_and_rbac(tmp_path):
    app = _context(tmp_path)
    with TestClient(app) as client:
        admin = _headers(client)
        read = _headers(client, "read")
        cashflow = client.post("/api/v1/cashflow", headers=admin, json={
            "periodo_ano": 2026, "periodo_mes": 8, "data_lancamento": "2026-08-29",
            "descricao": "Receita API", "tipo": "RECEITA", "categoria": "RECEITA_INDIRETA",
            "valor": "100.00", "boe": False,
        })
        assert cashflow.status_code == 201
        assert client.post("/api/v1/cashflow", headers=read, json={
            "periodo_ano": 2026, "periodo_mes": 8, "data_lancamento": "2026-08-29",
            "descricao": "Bloqueado", "tipo": "RECEITA", "categoria": "RECEITA_INDIRETA", "valor": "1"
        }).status_code == 403
        assert client.get("/api/v1/financial-flow?year=2026&month=8", headers=read).json()["summary"]["total_revenue"] == 100.0

        budget = client.post("/api/v1/budgets", headers=admin, json={
            "year": 2026, "month": 8, "entry_type": "RECEITA",
            "description": "Receita de serviços", "category": "RECEITA_INDIRETA",
            "budgeted_value": "120", "notes": None,
        })
        assert budget.status_code == 201
        budgets = client.get("/api/v1/budgets?year=2026&month=8", headers=read)
        assert budgets.status_code == 200
        assert budgets.json()["items"][0]["descricao"] == "Receita de serviços"
        assert budgets.json()["comparison"]["comparisons"][0]["description"] == "Receita de serviços"
        edited = client.patch(f"/api/v1/budgets/{budget.json()['id']}", headers=admin, json={
            "budgeted_value": "130", "notes": "Revisado",
        })
        assert edited.status_code == 200
        assert edited.json()["descricao"] == "Receita de serviços"
        assert budgets.json()["comparison"]["summary"]["actual_revenue"] == 100.0

        entity_id = client.get("/api/v1/entities", headers=admin).json()[0]["id"]
        target = client.post("/api/v1/targets", headers=admin, json={
            "entity_id": entity_id, "year": 2026, "month": 8, "indicator": "CONSULTAS",
            "target_value": "80", "actual_value": "100", "notes": None,
        })
        assert target.status_code == 201
        assert client.get("/api/v1/targets?year=2026&month=8&indicator=CONSULTAS", headers=read).status_code == 200
        ranking = client.get("/api/v1/ranking?year=2026&quarter=3", headers=read)
        assert ranking.status_code == 200 and ranking.json()["quarterly"][0]["classified"] is True
        assert {"quarterly", "annual"} == set(ranking.json())
        missing_parameters = client.get(
            "/api/v1/ranking?year=2027&quarter=1", headers=read
        )
        assert missing_parameters.status_code == 422
        assert missing_parameters.json()["detail"] == (
            "Os parâmetros do Ranking para 2027 não foram configurados."
        )
        assert client.get("/api/v1/dashboard?year=2026&month=8", headers=read).status_code == 200
        report = client.get("/api/v1/reports/annual?year=2026", headers=read)
        assert report.status_code == 200 and len(report.json()["rows"]) == 12
        assert client.get("/api/v1/reports/csv-validation?year=2026", headers=read).status_code == 200
        assert client.post("/api/v1/reports/csv-export", headers=read, json={"year": 2026}).status_code == 403
    app.state.engine.dispose()


def test_modular_dashboard_endpoints_enforce_area_permissions(tmp_path):
    app = _context(tmp_path)
    with TestClient(app) as client:
        finance = _headers(client, "finance")
        boe = _headers(client, "boe")

        assert client.get(
            "/api/v1/dashboard/financial?year=2026&month=8", headers=finance
        ).status_code == 200
        assert client.get(
            "/api/v1/dashboard/boe?year=2026&month=8", headers=finance
        ).status_code == 403
        assert client.get(
            "/api/v1/dashboard/boe?year=2026&month=8", headers=boe
        ).status_code == 200
        assert client.get(
            "/api/v1/dashboard/financial?year=2026&month=8", headers=boe
        ).status_code == 403
        targets = client.get(
            "/api/v1/dashboard/targets?year=2026&month=8&indicator=TODAS",
            headers=boe,
        )
        assert targets.status_code == 403


def test_budget_post_maps_api_description_to_domain_descricao(tmp_path):
    app = _context(tmp_path)
    with TestClient(app) as client:
        headers = _headers(client)
        response = client.post("/api/v1/budgets", headers=headers, json={
            "year": 2026,
            "month": 9,
            "description": "Licenciamento central",
            "entry_type": "DESPESA",
            "category": "ADMINISTRATIVO",
            "budgeted_value": "450.00",
            "notes": "Homologação BUG-ORC-001",
        })
        assert response.status_code == 201
        assert response.json()["descricao"] == "Licenciamento central"
        listing = client.get("/api/v1/budgets?year=2026&month=9", headers=headers)
        assert listing.status_code == 200
        assert listing.json()["items"][0]["descricao"] == "Licenciamento central"
    with app.state.session_factory() as session:
        persisted = session.scalar(select(BudgetEntry))
        assert persisted is not None
        assert persisted.descricao == "Licenciamento central"
    app.state.engine.dispose()


def test_dashboard_endpoints_forward_optional_period_filters(tmp_path, monkeypatch):
    captured = {}

    def boe(self, year, month, entity_id=None, start_month=None, end_month=None):
        captured["boe"] = (year, month, entity_id, start_month, end_month)
        return {"monthly": []}

    def targets(
        self, year, month, entity_id=None, indicator="TODAS",
        start_month=None, end_month=None,
    ):
        captured["targets"] = (
            year, month, entity_id, indicator, start_month, end_month,
        )
        return {"monthly": []}

    monkeypatch.setattr(DashboardService, "get_boe_dashboard", boe)
    monkeypatch.setattr(DashboardService, "get_targets_dashboard", targets)
    app = _context(tmp_path)
    with TestClient(app) as client:
        headers = _headers(client)
        assert client.get(
            "/api/v1/dashboard/boe"
            "?year=2026&month=7&entity_id=1&start_month=2&end_month=7",
            headers=headers,
        ).status_code == 200
        assert client.get(
            "/api/v1/dashboard/targets"
            "?year=2026&month=7&entity_id=1&indicator=CONSULTAS"
            "&start_month=3&end_month=6",
            headers=headers,
        ).status_code == 200

    assert captured["boe"] == (2026, 7, 1, 2, 7)
    assert captured["targets"] == (2026, 7, 1, "CONSULTAS", 3, 6)
    app.state.engine.dispose()


def test_boe_upload_validates_imports_and_generates_direct_revenue(tmp_path):
    app = _context(tmp_path)
    workbook = create_boe_workbook(tmp_path / "BOE - 07.26.xlsx")
    with TestClient(app) as client:
        headers = _headers(client)
        with workbook.open("rb") as handle:
            validated = client.post("/api/v1/boe/validate", headers=headers,
                                    files={"file": (workbook.name, handle)})
        assert validated.status_code == 200
        with workbook.open("rb") as handle:
            imported = client.post("/api/v1/boe/import", headers=headers,
                                   files={"file": (workbook.name, handle)})
        assert imported.status_code == 201
        history = client.get("/api/v1/boe", headers=headers)
        assert history.status_code == 200 and len(history.json()) == 1
        details = client.get(f"/api/v1/boe/{history.json()[0]['id']}", headers=headers)
        assert details.status_code == 200 and details.json()["total_entities"] == 2
    with app.state.session_factory() as db:
        direct = db.scalar(select(CashflowEntry).where(CashflowEntry.origem == "BOE"))
        assert direct is not None and direct.boe_import_id == imported.json()["id"]
    app.state.engine.dispose()


class FakeRemoteAPI:
    def __init__(self):
        self.health_calls = 0
        self.uploads = []

    def health(self):
        self.health_calls += 1
        return {
            "status": "ok", "version": "1.0.0", "environment": "SERVER",
            "database": "PostgreSQL central", "historical_import_enabled": False,
        }

    def upload(self, path, file_path):
        self.uploads.append((path, file_path))
        if path == "/api/v1/targets/import/validate":
            return {
                "metadata": {"file_name": "metas.xlsx", "detected_type": "META_REALIZADO", "year": 2026},
                "preview": [], "warnings": [], "errors": ["Sem dados"],
                "can_import": False,
                "totals": {"rows": 0, "target": 0, "actual": 0},
            }
        raise AssertionError(path)

    def get(self, path):
        zero = "0.0000"
        if path.startswith("/api/v1/dashboard/financial"):
            return {"kpis": {k: zero for k in (
                "opening_balance", "direct_revenue", "indirect_revenue",
                "total_revenue", "net_revenue", "total_expense", "applications",
                "redemptions", "bank_balance", "applied_balance")},
                "budget": {k: zero for k in (
                    "budgeted_revenue", "actual_revenue", "budgeted_expense",
                    "actual_expense", "result", "variance")}}
        if path.startswith("/api/v1/dashboard/boe"):
            return {"entities": [], "entity_count": 0, "queries": 0,
                    "total_value": zero, "unit_value": None}
        if path.startswith("/api/v1/dashboard/targets"):
            indicator = {"target": zero, "actual": zero,
                         "achievement_percentage": None}
            return {"queries": indicator, "registrations": indicator,
                    "indicator": "TODAS"}
        if path.startswith("/api/v1/boe"): return []
        if path == "/api/v1/catalog": return []
        if path == "/api/v1/entities": return []
        if path.startswith("/api/v1/financial-flow"):
            return {"items": [], "summary": {k: zero for k in ("direct_revenue", "indirect_revenue", "total_revenue", "total_expense", "applications", "redemptions", "operational_result", "cash_movement", "applied_balance")}}
        if path.startswith("/api/v1/budgets"):
            return {"items": [], "comparison": {"comparisons": [], "summary": {k: zero for k in ("budgeted_revenue", "actual_revenue", "budgeted_expense", "actual_expense", "budgeted_result", "actual_result")}}}
        if path.startswith("/api/v1/targets"):
            return {"entities": [], "comparison": {"comparisons": [], "summary": {"entity_count": 0, "target_total": zero, "actual_total": zero, "difference_total": zero, "achievement_percentage": None}}}
        if path.startswith("/api/v1/ranking"): return {"quarterly": [], "annual": []}
        if path.startswith("/api/v1/dashboard"):
            return {"year": 2026, "month": 8, "financial": {k: zero for k in ("total_revenue", "total_expense", "operational_result", "applications", "redemptions", "cash_movement", "applied_balance")},
                    "boe": {"has_data": False, "entities": 0, "queries": 0, "total_value": zero},
                    "budget": {k: zero for k in ("budgeted_revenue", "actual_revenue", "budgeted_expense", "actual_expense", "budgeted_result", "actual_result")},
                    "targets": {name: {"has_data": False, "target": zero, "actual": zero, "achievement_percentage": None} for name in ("queries", "registrations")}}
        if path.startswith("/api/v1/reports/annual"):
            keys = ("total_revenue", "total_expense", "operational_result", "applications", "redemptions", "cash_movement", "applied_balance", "boe_value", "budgeted_result")
            return {"year": 2026, "rows": [{"month": month, **{k: zero for k in keys}} for month in range(1, 13)]}
        raise AssertionError(path)
    def logout(self): pass
    def close(self): pass


def test_server_mode_main_window_never_opens_sqlite(qtbot, monkeypatch, tmp_path):
    from app.core.config import Settings
    import app.gui.main_window as module
    local_db = tmp_path / "ja_finance.db"
    local_db.write_bytes(b"unchanged")
    before = local_db.read_bytes()
    monkeypatch.setattr(module, "get_session_factory", lambda: (_ for _ in ()).throw(AssertionError("SQLite proibido")))
    settings = Settings("Finance", "production", False, f"sqlite:///{local_db.as_posix()}", "INFO", tmp_path)
    api = FakeRemoteAPI()
    window = module.MainWindow(settings, api_client=api)
    qtbot.addWidget(window)
    assert window._boe_session is None
    window._target_controller.validate_import_file(str(tmp_path / "metas.xlsx"))
    assert api.uploads == [
        ("/api/v1/targets/import/validate", str(tmp_path / "metas.xlsx"))
    ]
    assert local_db.read_bytes() == before


def test_server_administration_information_is_remote_and_local_actions_stay_blocked(
        qtbot, monkeypatch, tmp_path):
    from app.core.config import Settings
    import app.gui.main_window as module

    monkeypatch.setattr(
        module,
        "AdministrationService",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("AdministrationService local proibido no modo servidor")
        ),
    )
    monkeypatch.setattr(
        module,
        "get_session_factory",
        lambda: (_ for _ in ()).throw(AssertionError("SQLite proibido")),
    )
    api = FakeRemoteAPI()
    settings = Settings(
        "Finance", "production", False,
        f"sqlite:///{(tmp_path / 'proibido.db').as_posix()}", "INFO", tmp_path,
    )
    window = module.MainWindow(settings, api_client=api)
    qtbot.addWidget(window)
    page = window.pages["administracao"]

    qtbot.mouseClick(page.refresh_button, Qt.MouseButton.LeftButton)

    assert api.health_calls == 2
    assert page.fields["environment"].text() == "SERVER"
    assert page.fields["database"].text() == "PostgreSQL central"
    assert page.fields["version"].text() == "1.0.0"
    assert page.fields["revision"].text() == "Não informado pela API"
    assert page.fields["logs"].text() == "Indisponível no modo servidor"
    assert page.status.text() == "Informações centrais atualizadas."
    assert not page.logs_button.isEnabled()
    assert not page.backup_button.isEnabled()
    assert not page.import_button.isEnabled()


def test_dev_api_enables_historical_import_for_dev_sqlite(qtbot, monkeypatch, tmp_path):
    from app.core.config import Settings
    import app.gui.main_window as module

    class DevAPI(FakeRemoteAPI):
        def health(self):
            self.health_calls += 1
            return {
                "status": "ok", "version": "1.0.0", "environment": "DEV",
                "database": "SQLite DEV", "historical_import_enabled": True,
            }

    class Session:
        def close(self):
            pass

    monkeypatch.setattr(module, "get_session_factory", lambda: lambda: Session())
    api = DevAPI()
    settings = Settings(
        "Finance", "development", False,
        f"sqlite:///{(tmp_path / 'finance_dev.db').as_posix()}", "INFO", tmp_path,
    )
    window = module.MainWindow(settings, api_client=api)
    qtbot.addWidget(window)
    page = window.pages["administracao"]

    qtbot.mouseClick(page.refresh_button, Qt.MouseButton.LeftButton)

    assert page.fields["environment"].text() == "DEV"
    assert page.fields["database"].text() == "SQLite DEV"
    assert page.import_button.isEnabled()
    assert not page.logs_button.isEnabled()
    assert not page.backup_button.isEnabled()


def test_remote_budget_service_sends_and_preserves_description():
    from app.services.remote_services import RemoteBudgetService

    class API:
        def __init__(self): self.payloads = []
        def post(self, path, payload):
            self.payloads.append((path, payload))
            return {"id": 1, "periodo_ano": 2026, "periodo_mes": 8,
                    "descricao": payload["description"], "tipo": payload["entry_type"],
                    "categoria": payload["category"], "valor_orcado": payload["budgeted_value"],
                    "observacao": payload["notes"]}
        def patch(self, path, payload):
            self.payloads.append((path, payload))
            return {"id": 1, "periodo_ano": 2026, "periodo_mes": 8,
                    "descricao": payload["description"], "tipo": "DESPESA",
                    "categoria": "ADMINISTRATIVO", "valor_orcado": payload["budgeted_value"],
                    "observacao": payload["notes"]}

    api = API()
    service = RemoteBudgetService(api)
    created = service.create_budget(
        year=2026, month=8, entry_type="DESPESA", category="ADMINISTRATIVO",
        description="Licenças", budgeted_value="100", notes=None,
    )
    updated = service.update_budget(
        created.id, description="Licenças anuais", budgeted_value="120", notes="Revisado",
    )
    assert api.payloads[0][0] == "/api/v1/budgets"
    assert api.payloads[0][1]["description"] == "Licenças"
    assert updated.descricao == "Licenças anuais"


def test_remote_budget_catalog_uses_only_active_revenue_and_expense():
    from app.services.remote_services import RemoteCatalogService

    class API:
        def get(self, path):
            assert path == "/api/v1/catalog"
            return [
                {"descricao": "Receita", "categoria": "RECEITA_INDIRETA", "tipo": "RECEITA", "ativa": True},
                {"descricao": "Despesa", "categoria": "ADMINISTRATIVO", "tipo": "DESPESA", "ativa": True},
                {"descricao": "Aplicação", "categoria": "INVESTIMENTO", "tipo": "APLICACAO", "ativa": True},
                {"descricao": "Inativa", "categoria": "OUTROS", "tipo": "DESPESA", "ativa": False},
            ]

    options = RemoteCatalogService(API()).list_budget_options()
    assert [(item.description, item.movement_type) for item in options] == [
        ("Receita", "RECEITA"), ("Despesa", "DESPESA")
    ]


def test_remote_target_import_uses_authenticated_api_upload_only(tmp_path):
    from app.services.remote_services import RemoteTargetService

    class API:
        def __init__(self):
            self.uploads = []

        def upload(self, path, file_path, **kwargs):
            self.uploads.append((path, file_path, kwargs))
            return {"can_import": path.endswith("validate")}

    file_path = tmp_path / "metas.xlsx"
    file_path.write_bytes(b"workbook")
    api = API()
    service = RemoteTargetService(api)

    assert service.validate_import(file_path)["can_import"] is True
    service.import_file(file_path)
    assert api.uploads == [
        ("/api/v1/targets/import/validate", str(file_path), {}),
        ("/api/v1/targets/import", str(file_path), {"import_file": True}),
    ]
