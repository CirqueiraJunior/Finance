from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cashflow_catalog_entry import CashflowCatalogEntry
from app.models.cashflow_entry import CashflowEntry
from app.models.investment_movement import InvestmentMovement
from app.repositories.cashflow_catalog_repository import CashflowCatalogRepository
from app.services.cashflow_catalog_service import CashflowCatalogService
from app.services.financial_import_service import (
    FinancialImportService, FinancialImportValidationError,
)
from finance_server.app_factory import create_app
from finance_server.config import ServerSettings
from finance_server.models import AuditLog, User, UserRole
from finance_server.security import hash_password


PASSWORD = "Strong!Pass123"


def financial_workbook(
    path: Path, *, invalid=False, only_direct=False, year=2026, month="Abril"
) -> Path:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Lancamentos"
    sheet.append(["Financeiro"])
    sheet.append(["Ano", "Mês", "Descrição", "Observação", "Categoria", "Tipo", "Valor", "BOE"])
    sheet.append([year, month, "Receita BOE", None, "Receita Direta", "Receita", 900, "Sim"])
    if not only_direct:
        sheet.append([year, month, "Mensalidade", "Origem teste", "Receita Indireta", "Receita", 100, "Não"])
        sheet.append([year, month, "Energia", None, "Administrativo", "Despesas" if invalid else "Despesa", 40, "Não"])
        sheet.append([year, month, "Aplicação mensal", None, "Investimento", "Aplicação", 20, "Não"])
        sheet.append([year, month, "Resgate mensal", None, "Resgate", "Resgate", 5, "Não"])
    workbook.save(path)
    return path


def seed_catalog(db: Session) -> None:
    db.add_all([
        CashflowCatalogEntry(descricao="Receita BOE", categoria="RECEITA_DIRETA", tipo="RECEITA", ativa=True),
        CashflowCatalogEntry(descricao="Mensalidade", categoria="RECEITA_INDIRETA", tipo="RECEITA", ativa=True),
        CashflowCatalogEntry(descricao="Energia", categoria="ADMINISTRATIVO", tipo="DESPESA", ativa=True),
        CashflowCatalogEntry(descricao="Aplicação mensal", categoria="INVESTIMENTO", tipo="APLICACAO", ativa=True),
        CashflowCatalogEntry(descricao="Resgate mensal", categoria="RESGATE", tipo="RESGATE", ativa=True),
    ])
    db.flush()


def service(db: Session) -> FinancialImportService:
    return FinancialImportService(
        db, CashflowCatalogService(CashflowCatalogRepository(db))
    )


def test_validation_preview_warning_and_no_direct_revenue(db_session, tmp_path):
    seed_catalog(db_session)
    path = financial_workbook(tmp_path / "Financeiro.xlsx")

    validation = service(db_session).validate(path)

    assert validation.can_import is True
    assert len(validation.preview) == 5
    assert validation.preview[0]["skip"] is True
    assert any("Receita Direta" in warning for warning in validation.warnings)


def test_january_2026_imports_historical_direct_revenue_once(db_session, tmp_path):
    seed_catalog(db_session)
    path = financial_workbook(
        tmp_path / "Janeiro.xlsx", only_direct=True, month="Janeiro"
    )
    importer = service(db_session)

    validation, entries = importer.stage_import(path)
    db_session.commit()

    assert validation.can_import is True
    assert validation.preview[0].get("skip") is not True
    assert validation.warnings == (
        "Receita Direta de 01/2026 importada da base histórica por ausência de BOE 12/2025.",
    )
    assert len(entries) == 1
    entry = db_session.scalar(select(CashflowEntry))
    assert (entry.periodo_ano, entry.periodo_mes) == (2026, 1)
    assert (entry.origem, entry.categoria) == ("MANUAL", "RECEITA_DIRETA")
    assert importer.validate(path).can_import is False


def test_january_historical_direct_is_ignored_when_previous_boe_exists(
    db_session, tmp_path,
):
    from app.models.boe_import import BOEImport

    seed_catalog(db_session)
    db_session.add(BOEImport(
        periodo_ano=2025, periodo_mes=12, nome_arquivo="BOE-12.25.xlsx",
        caminho_origem="fixture", hash_arquivo="9" * 64,
        quantidade_entidades=1, quantidade_inconsistencias=0,
        valor_total=900, status="imported",
    ))
    db_session.commit()
    path = financial_workbook(
        tmp_path / "Janeiro.xlsx", only_direct=True, month="Janeiro"
    )

    validation = service(db_session).validate(path)

    assert validation.can_import is False
    assert validation.preview[0]["skip"] is True


def test_import_stages_all_supported_types_and_repeat_is_blocked(db_session, tmp_path):
    seed_catalog(db_session)
    path = financial_workbook(tmp_path / "Financeiro.xlsx")
    importer = service(db_session)

    validation, entries = importer.stage_import(path)
    db_session.commit()

    assert len(entries) == 4
    assert validation.can_import is True
    assert db_session.scalar(select(func.count()).select_from(CashflowEntry)) == 2
    assert db_session.scalar(select(func.count()).select_from(InvestmentMovement)) == 2
    assert db_session.scalar(select(func.count()).select_from(CashflowEntry).where(
        CashflowEntry.categoria == "RECEITA_DIRETA"
    )) == 0
    repeated = importer.validate(path)
    assert repeated.can_import is False
    assert repeated.duplicates == 4


def test_blocking_error_and_atomic_rollback(db_session, tmp_path, monkeypatch):
    seed_catalog(db_session)
    invalid = financial_workbook(tmp_path / "Inválido.xlsx", invalid=True)
    with pytest.raises(FinancialImportValidationError):
        service(db_session).stage_import(invalid)

    valid = financial_workbook(tmp_path / "Financeiro.xlsx")
    original_flush = Session.flush

    def fail_flush(session, *args, **kwargs):
        if any(isinstance(item, (CashflowEntry, InvestmentMovement)) for item in session.new):
            raise RuntimeError("falha controlada")
        return original_flush(session, *args, **kwargs)

    monkeypatch.setattr(Session, "flush", fail_flush)
    with pytest.raises(RuntimeError, match="falha controlada"):
        service(db_session).stage_import(valid)
    assert db_session.scalar(select(func.count()).select_from(CashflowEntry)) == 0
    assert db_session.scalar(select(func.count()).select_from(InvestmentMovement)) == 0


@pytest.fixture
def financial_api(tmp_path):
    settings = ServerSettings(
        f"sqlite:///{(tmp_path / 'server.db').as_posix()}", "s" * 64
    )
    app = create_app(settings, create_schema=True)
    with app.state.session_factory() as db:
        db.add(User(
            nome="Admin", email="admin@test.local", username="admin",
            password_hash=hash_password(PASSWORD),
            perfil=UserRole.ADMINISTRATOR.value, ativo=True,
        ))
        seed_catalog(db)
        db.commit()
    with TestClient(app) as client:
        yield client, app, tmp_path
    app.state.engine.dispose()


def headers(client):
    result = client.post("/api/v1/auth/login", json={
        "identifier": "admin", "password": PASSWORD,
    }).json()
    return {"Authorization": f"Bearer {result['access_token']}"}


def upload(client, endpoint, path, auth):
    with path.open("rb") as handle:
        return client.post(endpoint, headers=auth, files={"file": (path.name, handle)})


def test_api_validates_imports_and_audits_atomically(financial_api):
    client, app, tmp_path = financial_api
    path = financial_workbook(tmp_path / "Financeiro.xlsx")
    auth = headers(client)

    validation = upload(client, "/api/v1/financial-import/validate", path, auth)
    imported = upload(client, "/api/v1/financial-import", path, auth)

    assert validation.status_code == 200
    assert validation.json()["can_import"] is True
    assert imported.status_code == 201
    assert imported.json()["imported"] == 4
    with app.state.session_factory() as db:
        audit = db.scalar(select(AuditLog).where(AuditLog.action == "FINANCIAL_IMPORTED"))
        assert audit is not None
        assert audit.details["imported"] == 4
        assert db.scalar(select(func.count()).select_from(CashflowEntry).where(
            CashflowEntry.categoria == "RECEITA_DIRETA"
        )) == 0


def test_api_rejects_direct_revenue_only_without_writing(financial_api):
    client, app, tmp_path = financial_api
    path = financial_workbook(tmp_path / "Somente BOE.xlsx", only_direct=True)

    response = upload(client, "/api/v1/financial-import", path, headers(client))

    assert response.status_code == 422
    assert response.json()["detail"]["can_import"] is False
    with app.state.session_factory() as db:
        assert db.scalar(select(func.count()).select_from(CashflowEntry)) == 0
        assert db.scalar(select(AuditLog).where(AuditLog.action == "FINANCIAL_IMPORTED")) is None
