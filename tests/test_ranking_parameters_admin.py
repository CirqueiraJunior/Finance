from copy import deepcopy

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api_client.client import APIClient, AuthenticatedUser
from app.core.config import Settings
from app.gui.main_window import MainWindow
from tests.test_sprint12a1_centralization import FakeRemoteAPI, _context, _headers


OFFICIAL = {
    "minimum_achievement_percent": "100",
    "billing_level_1_min": "100",
    "billing_level_1_points": 5,
    "billing_level_2_min": "110",
    "billing_level_2_points": 6,
    "billing_level_3_min": "150",
    "billing_level_3_points": 7,
    "acquisition_level_1_min": "1",
    "acquisition_level_1_points": 2,
    "acquisition_level_2_min": "8",
    "acquisition_level_2_points": 3,
    "acquisition_level_3_min": "16",
    "acquisition_level_3_points": 4,
    "zero_cancellation_points": 1,
    "positive_cancellation_points": 0,
    "first_place_award": "3000",
    "second_place_award": "2000",
    "third_place_award": "1000",
}


def test_ranking_parameter_api_is_administrator_only_and_returns_official_2026(tmp_path):
    app = _context(tmp_path)
    with TestClient(app) as client:
        admin = _headers(client, "admin")
        response = client.get("/api/v1/ranking/parameters/2026", headers=admin)
        assert response.status_code == 200
        assert response.json()["year"] == 2026
        for name, expected in OFFICIAL.items():
            assert float(response.json()[name]) == float(expected)

        for identifier in ("finance", "boe", "read"):
            assert client.get(
                "/api/v1/ranking/parameters/2026",
                headers=_headers(client, identifier),
            ).status_code == 403
    app.state.engine.dispose()


def test_ranking_parameter_api_updates_creates_and_never_inherits_missing_year(tmp_path):
    app = _context(tmp_path)
    with TestClient(app) as client:
        admin = _headers(client, "admin")
        assert client.get(
            "/api/v1/ranking/parameters/2027", headers=admin
        ).status_code == 404

        changed = {**OFFICIAL, "first_place_award": "3500"}
        updated = client.put(
            "/api/v1/ranking/parameters/2026", headers=admin, json=changed
        )
        assert updated.status_code == 200
        assert float(updated.json()["first_place_award"]) == 3500

        created = client.put(
            "/api/v1/ranking/parameters/2027", headers=admin, json=OFFICIAL
        )
        assert created.status_code == 200
        assert created.json()["year"] == 2027

        ranking = client.get("/api/v1/ranking?year=2026&quarter=1", headers=admin)
        assert ranking.status_code == 200
        assert set(ranking.json()) == {"quarterly", "annual"}
    app.state.engine.dispose()


@pytest.mark.parametrize(
    "payload",
    [
        {key: value for key, value in OFFICIAL.items() if key != "third_place_award"},
        {**OFFICIAL, "billing_level_2_min": "99"},
        {**OFFICIAL, "acquisition_level_3_min": "8"},
        {**OFFICIAL, "first_place_award": "-1"},
        {**OFFICIAL, "billing_level_1_points": -1},
    ],
)
def test_ranking_parameter_api_rejects_partial_unordered_or_negative_payloads(
    tmp_path, payload
):
    app = _context(tmp_path)
    with TestClient(app) as client:
        response = client.put(
            "/api/v1/ranking/parameters/2027",
            headers=_headers(client, "admin"),
            json=payload,
        )
        assert response.status_code == 422
        assert client.get(
            "/api/v1/ranking/parameters/2027",
            headers=_headers(client, "admin"),
        ).status_code == 404
    app.state.engine.dispose()


def test_api_client_uses_parameter_contract_and_handles_missing_year(monkeypatch):
    client = APIClient("http://finance.test")
    calls = []

    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return None if method == "GET" else {"year": 2027}

    monkeypatch.setattr(client, "_request", request)
    assert client.get_ranking_parameters(2027) is None
    assert client.save_ranking_parameters(2027, OFFICIAL) == {"year": 2027}
    assert calls == [
        ("GET", "/api/v1/ranking/parameters/2027", {"_allow_not_found": True}),
        ("PUT", "/api/v1/ranking/parameters/2027", {"json": OFFICIAL}),
    ]
    client.close()


class RankingAPI(FakeRemoteAPI):
    def __init__(self):
        super().__init__()
        self.parameters = {2026: {"id": 1, "year": 2026, **deepcopy(OFFICIAL)}}
        self.saved = []

    def get_ranking_parameters(self, year):
        value = self.parameters.get(year)
        return deepcopy(value) if value else None

    def save_ranking_parameters(self, year, payload):
        self.saved.append((year, deepcopy(payload)))
        value = {"id": len(self.parameters) + 1, "year": year, **deepcopy(payload)}
        self.parameters[year] = value
        return deepcopy(value)


def _window(tmp_path, role, api=None):
    settings = Settings(
        "Finance", "development", False,
        f"sqlite:///{(tmp_path / 'unused.db').as_posix()}", "INFO", tmp_path,
    )
    return MainWindow(
        settings,
        api_client=api or RankingAPI(),
        authenticated_user=AuthenticatedUser(1, role.title(), role, False),
    )


def test_only_administrator_sees_ranking_parameter_block(qtbot, tmp_path):
    windows = []
    for role in (
        "ADMINISTRADOR", "GESTOR", "OPERADOR_FINANCEIRO", "OPERADOR_BOE", "CONSULTA"
    ):
        window = _window(tmp_path, role)
        qtbot.addWidget(window)
        windows.append(window)
        visible = window.pages["administracao"].ranking_parameters_widget.isVisibleTo(
            window.pages["administracao"]
        )
        assert visible is (role == "ADMINISTRADOR")


def test_administrator_loads_existing_starts_blank_year_and_saves(qtbot, tmp_path):
    api = RankingAPI()
    window = _window(tmp_path, "ADMINISTRADOR", api)
    qtbot.addWidget(window)
    widget = window.pages["administracao"].ranking_parameters_widget

    widget.load_button.click()
    assert widget.fields["billing_level_2_min"].value() == 110
    assert widget.fields["first_place_award"].value() == 3000

    widget.year.setValue(2027)
    widget.load_button.click()
    assert all(field.value() == 0 for field in widget.fields.values())
    assert "Nova configuração para 2027" in widget.status.text()

    widget.show_parameters({"id": 2, "year": 2027, **OFFICIAL})
    widget.save_button.click()
    assert api.saved[-1][0] == 2027
    assert api.saved[-1][1]["billing_level_3_points"] == 7
    assert "salvos com sucesso" in widget.status.text()


def test_gui_rejects_unordered_ranges_before_api_call(qtbot, tmp_path):
    api = RankingAPI()
    window = _window(tmp_path, "ADMINISTRADOR", api)
    qtbot.addWidget(window)
    widget = window.pages["administracao"].ranking_parameters_widget
    widget.show_parameters({"id": 1, "year": 2026, **OFFICIAL})
    widget.fields["billing_level_2_min"].setValue(99)

    widget.save_button.click()

    assert api.saved == []
    assert "ordem crescente" in widget.status.text()
