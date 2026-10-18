from test_budget_import_api import _budget_workbook, _headers, budget_import_context
from sqlalchemy import select
from app.models.budget_entry import BudgetEntry

def _post(client, endpoint, path, headers, token=None):
    with path.open("rb") as handle:
        return client.post(
            endpoint, headers=headers,
            files={"file": (path.name, handle)},
            data={"preview_authorization": token} if token else {},
        )

def test_import_without_token_rejected(budget_import_context):
    client, app, tmp_path = budget_import_context
    path = _budget_workbook(tmp_path / "Orçamento 2026.xlsx")
    response = _post(client, "/api/v1/budgets/import", path, _headers(client))
    assert response.status_code == 409
    with app.state.session_factory() as db:
        assert db.scalar(select(BudgetEntry.id).limit(1)) is None

def test_modified_token_rejected(budget_import_context):
    client, app, tmp_path = budget_import_context
    path = _budget_workbook(tmp_path / "Orçamento 2026.xlsx")
    headers = _headers(client)
    token = _post(client, "/api/v1/budgets/import/validate", path, headers).json()["preview_authorization"]
    response = _post(client, "/api/v1/budgets/import", path, headers, token + "X")
    assert response.status_code == 409

def test_stale_database_preview_rejected(budget_import_context):
    client, app, tmp_path = budget_import_context
    path = _budget_workbook(tmp_path / "Orçamento 2026.xlsx")
    headers = _headers(client)
    token = _post(client, "/api/v1/budgets/import/validate", path, headers).json()["preview_authorization"]
    with app.state.session_factory() as db:
        db.add(BudgetEntry(
            periodo_ano=2026, periodo_mes=1,
            tipo="RECEITA", categoria="RECEITA_DIRETA",
            descricao="Concorrente", valor_orcado=99))
        db.commit()
    response = _post(client, "/api/v1/budgets/import", path, headers, token)
    assert response.status_code == 409
