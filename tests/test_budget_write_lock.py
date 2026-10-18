"""Testes isolados do bloqueio cooperativo de Orçamento."""
from unittest.mock import Mock
import pytest

from app.services.budget_write_lock import (
    BUDGET_WRITE_LOCK_ID, acquire_budget_write_lock,
)


def _session(dialect):
    session = Mock()
    session.get_bind.return_value.dialect.name = dialect
    return session


def test_identificador_eh_valido_para_bigint_assinado():
    assert 0 < BUDGET_WRITE_LOCK_ID < 2**63


def test_postgres_usa_bloqueio_transacional():
    session = _session("postgresql")
    assert acquire_budget_write_lock(session) is True
    session.execute.assert_called_once()
    statement, params = session.execute.call_args.args
    assert "pg_advisory_xact_lock" in str(statement)
    assert params == {"lock_id": BUDGET_WRITE_LOCK_ID}


def test_sqlite_nao_simula_bloqueio_postgres():
    session = _session("sqlite")
    assert acquire_budget_write_lock(session) is False
    session.execute.assert_not_called()


def test_dialeto_nao_suportado_falha_fechado():
    session = _session("mysql")
    with pytest.raises(RuntimeError, match="indisponível"):
        acquire_budget_write_lock(session)
    session.execute.assert_not_called()
