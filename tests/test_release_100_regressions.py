import pytest
from fastapi.testclient import TestClient
from PySide6.QtCore import Qt

from app.gui.pages.dashboard import DashboardPage
from tests.test_sprint12a1_centralization import _context, _headers


def test_financial_filters_independent_from_empty_boe_and_targets(qtbot):
    page = DashboardPage()
    qtbot.addWidget(page)

    page.boe_entity_filter.set_selected_values(())
    page.target_entity_filter.set_selected_values(())

    filters = page.selected_dashboard_filters(areas={"financial"})
    assert "financial_start_year" in filters
    assert "financial_end_year" in filters

    with pytest.raises(ValueError, match="Entidade BOE"):
        page.selected_dashboard_filters(areas={"boe"})

    with pytest.raises(ValueError, match="Entidade de Metas"):
        page.selected_dashboard_filters(areas={"targets"})


def test_audit_api_returns_nominal_user(tmp_path):
    app = _context(tmp_path)

    try:
        with TestClient(app) as client:
            headers = _headers(client, "admin")

            response = client.post(
                "/api/v1/cashflow",
                headers=headers,
                json={
                    "periodo_ano": 2026,
                    "periodo_mes": 8,
                    "data_lancamento": "2026-08-29",
                    "descricao": "Teste de auditoria nominal",
                    "tipo": "RECEITA",
                    "categoria": "RECEITA_INDIRETA",
                    "valor": "100.00",
                    "boe": False,
                },
            )
            assert response.status_code == 201

            audit_response = client.get("/api/v1/audit", headers=headers)
            assert audit_response.status_code == 200

            records = audit_response.json()
            assert any(
                item.get("user_name") == "Admin"
                and item.get("user_id") is not None
                for item in records
            )
    finally:
        app.state.engine.dispose()