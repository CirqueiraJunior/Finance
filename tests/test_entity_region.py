from fastapi.testclient import TestClient
from PySide6.QtWidgets import QFormLayout

from app.gui.controllers.registration_controller import RemoteRegistrationController
from app.gui.pages.cadastros import CadastrosPage, EntityDialog
from app.models.entity import Entity
from app.repositories.entity_repository import EntityRepository
from app.services.entity_service import EntityService
from finance_server.app_factory import create_app
from finance_server.config import ServerSettings
from finance_server.models import User, UserRole
from finance_server.security import hash_password


PASSWORD = "Strong!Pass123"


def test_entity_service_persists_region_and_preserves_historical_location(db_session):
    service = EntityService(EntityRepository(db_session))
    entity = service.create_entity(
        codigo_entidade=7501,
        nome="CDL Goiânia",
        municipio="Goiânia",
        uf="GO",
        regiao="centro",
    )

    updated = service.update_entity(
        entity.id,
        nome="CDL Goiânia Atualizada",
        regiao="LESTE",
    )
    service.set_active(entity.id, False)

    assert updated.regiao == "LESTE"
    assert updated.municipio == "Goiânia"
    assert updated.uf == "GO"
    assert updated.ativa is False


def test_entity_dialog_and_table_show_only_official_regions(qtbot):
    dialog = EntityDialog()
    page = CadastrosPage()
    qtbot.addWidget(dialog)
    qtbot.addWidget(page)

    assert [dialog.region.itemText(index) for index in range(dialog.region.count())] == [
        "Norte", "Noroeste", "Centro", "Leste", "Sul",
    ]
    assert [dialog.region.itemData(index) for index in range(dialog.region.count())] == [
        "NORTE", "NOROESTE", "CENTRO", "LESTE", "SUL",
    ]
    labels = [
        dialog.layout().itemAt(
            index, QFormLayout.ItemRole.LabelRole
        ).widget().text()
        for index in range(dialog.layout().rowCount())
        if dialog.layout().itemAt(index, QFormLayout.ItemRole.LabelRole) is not None
        and hasattr(
            dialog.layout().itemAt(
                index, QFormLayout.ItemRole.LabelRole
            ).widget(),
            "text",
        )
    ]
    assert "Região" in labels
    assert "Município" not in labels
    assert "UF" not in labels

    page.show_entities([
        Entity(
            id=1, codigo_entidade=7501, nome="CDL Goiânia",
            municipio="Goiânia", uf="GO", regiao="NOROESTE", ativa=True,
        )
    ])
    assert page.entity_table.columnCount() == 6
    assert page.entity_table.horizontalHeaderItem(3).text() == "Região"
    assert page.entity_table.item(0, 3).text() == "Noroeste"
    assert page.entity_guidance.text() == (
        "Selecione uma Entidade para consultar ou realizar as ações disponíveis."
    )


def test_entity_api_create_update_and_response_preserve_historical_location(tmp_path):
    settings = ServerSettings(
        f"sqlite:///{(tmp_path / 'entities.db').as_posix()}", "s" * 64
    )
    app = create_app(settings, create_schema=True)
    with app.state.session_factory() as db:
        db.add(User(
            nome="Admin", email="admin@example.com", username="admin",
            password_hash=hash_password(PASSWORD),
            perfil=UserRole.ADMINISTRATOR.value, ativo=True,
        ))
        db.commit()

    with TestClient(app) as client:
        pair = client.post("/api/v1/auth/login", json={
            "identifier": "admin", "password": PASSWORD,
        }).json()
        headers = {"Authorization": f"Bearer {pair['access_token']}"}
        created = client.post("/api/v1/entities", headers=headers, json={
            "codigo_entidade": 7501,
            "nome": "CDL Goiânia",
            "municipio": "Goiânia",
            "uf": "GO",
            "regiao": "CENTRO",
        })
        entity_id = created.json()["id"]
        updated = client.patch(
            f"/api/v1/entities/{entity_id}", headers=headers,
            json={"nome": "CDL Goiânia", "regiao": "SUL", "ativa": False},
        )
        listing = client.get("/api/v1/entities", headers=headers)

    assert created.status_code == 201
    assert created.json()["regiao"] == "CENTRO"
    assert updated.status_code == 200
    assert updated.json()["regiao"] == "SUL"
    assert updated.json()["municipio"] == "Goiânia"
    assert updated.json()["uf"] == "GO"
    assert listing.json()[0]["regiao"] == "SUL"
    app.state.engine.dispose()


def test_remote_toggle_sends_region_without_historical_location(qtbot):
    class API:
        def __init__(self):
            self.payload = None

        def get(self, path):
            if path == "/api/v1/catalog":
                return []
            return [{
                "id": 1, "codigo_entidade": 7501, "nome": "CDL Goiânia",
                "nome_oficial": None, "municipio": "Goiânia", "uf": "GO",
                "regiao": "NORTE", "sigla": "GYN", "ativa": True,
                "aliases": [],
            }]

        def patch(self, path, payload):
            self.payload = payload
            return {}

    api = API()
    page = CadastrosPage()
    qtbot.addWidget(page)
    controller = RemoteRegistrationController(page, api)
    page.entity_table.selectRow(0)

    controller.toggle_entity()

    assert api.payload["regiao"] == "NORTE"
    assert api.payload["ativa"] is False
    assert "municipio" not in api.payload
    assert "uf" not in api.payload
