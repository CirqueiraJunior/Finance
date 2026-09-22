"""Integrity regressions using isolated databases, never the central server."""
from datetime import date
from decimal import Decimal
import logging
from types import SimpleNamespace

import pytest
from sqlalchemy import event, select, func
from sqlalchemy.exc import IntegrityError

from app.core.exceptions import CashflowDuplicateBOEError, CashflowIntegrityError
from app.models.boe_import import BOEImport
from app.models.boe_entity_total import BOEEntityTotal
from app.models.boe_import_issue import BOEImportIssue
from app.models.cashflow_entry import CashflowEntry
from app.models.entity import Entity
from app.repositories.cashflow_repository import CashflowRepository
from app.services.cashflow_service import CashflowService
from finance_server.models import AuditLog
from tests.boe_helpers import add_boe_import, create_boe_workbook
from tests.test_multiuser_api import api_context, auth, login  # noqa: F401


@pytest.fixture(autouse=True)
def isolate_log_capture(monkeypatch, caplog):
    # Earlier migration tests reconfigure logging with Alembic's fileConfig.
    logger = logging.getLogger("app.services.cashflow_service")
    monkeypatch.setattr(logger, "disabled", False)
    monkeypatch.setattr(logger, "propagate", True)
    caplog.set_level(logging.ERROR, logger=logger.name)


def seed_cashflow(session):
    return CashflowService(CashflowRepository(session)).create_indirect_revenue(
        year=2026, month=3, entry_date=date(2026, 3, 1),
        description="Existing revenue", value=Decimal("10.00"),
    ).id


@pytest.mark.parametrize("state,constraint,expected", [
    ("23505", "ix_cashflow_entries_boe_import_id", CashflowDuplicateBOEError),
    ("23505", "cashflow_entries_pkey", CashflowIntegrityError),
    ("23505", "other_unique", CashflowIntegrityError),
    ("23503", "ix_cashflow_entries_boe_import_id", CashflowIntegrityError),
    ("23505", None, CashflowIntegrityError),
])
def test_postgresql_structured_diagnostics(db_session, monkeypatch, caplog, state, constraint, expected):
    repository = CashflowRepository(db_session)
    service = CashflowService(repository)
    original = Exception("Sensitive driver message must not be logged")
    original.sqlstate = state
    original.diag = SimpleNamespace(constraint_name=constraint)

    def fail(entry):
        raise IntegrityError("SQL not for public display", {"private": "hidden"}, original)

    monkeypatch.setattr(repository, "add", fail)
    pending = BOEImport(periodo_ano=2026, periodo_mes=3)
    db_session.add(pending)
    with pytest.raises(expected):
        service._persist(CashflowEntry(boe_import_id=123), commit=False)
    assert pending not in db_session
    assert not db_session.in_transaction()
    assert "Sensitive driver" not in caplog.text
    assert "hidden" not in caplog.text
    if expected is CashflowIntegrityError:
        assert "Cashflow persistence integrity failure" in caplog.text


def test_sqlite_actual_boe_unique_constraint(db_session, monkeypatch):
    repository = CashflowRepository(db_session)
    service = CashflowService(repository)
    boe = add_boe_import(db_session)
    boe.valor_total = Decimal("10")
    db_session.commit()
    existing = service.create_direct_revenue_from_boe(boe)
    existing_id = existing.id
    # Bypass only the preflight to reproduce the real database race/constraint.
    monkeypatch.setattr(repository, "exists_for_boe_import", lambda _: False)
    with pytest.raises(CashflowDuplicateBOEError):
        service.create_direct_revenue_from_boe(boe)
    assert db_session.scalars(select(CashflowEntry.id)).all() == [existing_id]


@pytest.mark.parametrize("fail_pk", [False, True])
def test_boe_endpoint_pk_rollback_and_normal_import(api_context, tmp_path, fail_pk, caplog):
    client, app, _, _ = api_context
    headers = auth(login(client).json())
    with app.state.session_factory() as session:
        session.add(Entity(codigo_entidade=7501, nome="CDL GOIANIA/GO"))
        session.commit()
        existing_id = seed_cashflow(session)
    path = create_boe_workbook(
        tmp_path / "BOE - 03.26.xlsx",
        rows=[(7501, "NOME DIVERGENTE", 100, Decimal("6.9300"))],
    )

    def collide(mapper, connection, entry):
        if entry.boe_import_id is not None:
            entry.id = existing_id

    if fail_pk:
        event.listen(CashflowEntry, "before_insert", collide)
    try:
        response = client.post("/api/v1/boe/import", headers=headers,
                               files={"file": (path.name, path.read_bytes())})
    finally:
        if fail_pk:
            event.remove(CashflowEntry, "before_insert", collide)
    with app.state.session_factory() as session:
        assert session.get(CashflowEntry, existing_id) is not None
        for model in (BOEImport, BOEEntityTotal, BOEImportIssue):
            assert session.scalar(select(func.count()).select_from(model)) == (0 if fail_pk else 1)
        assert session.scalar(select(func.count()).select_from(CashflowEntry)) == (1 if fail_pk else 2)
        audits = session.scalars(select(AuditLog).where(AuditLog.action == "BOE_IMPORTED")).all()
        assert len(audits) == (0 if fail_pk else 1)
    if fail_pk:
        assert response.status_code == 500
        assert "operação foi cancelada" in response.json()["detail"]
        assert "já possui uma Receita Direta" not in response.text
        for technical in ("Traceback", "INSERT", "cashflow_entries_pkey", "UNIQUE constraint"):
            assert technical not in response.text
        assert "Cashflow persistence integrity failure" in caplog.text
    else:
        assert response.status_code == 201


def test_api_reports_actual_boe_duplicate_as_conflict(api_context, monkeypatch, tmp_path):
    from app.services.boe_service import BOEService
    client, _, _, _ = api_context
    headers = auth(login(client).json())

    def duplicate(self, path):
        raise CashflowDuplicateBOEError("Esta importação BOE já possui uma Receita Direta.")

    monkeypatch.setattr(BOEService, "import_file", duplicate)
    response = client.post("/api/v1/boe/import", headers=headers,
                           files={"file": ("test.xlsx", b"isolated test")})
    assert response.status_code == 409
    assert "já possui uma Receita Direta" in response.json()["detail"]
