"""Testes opt-in de concorrência PostgreSQL para o bloqueio do orçamento.

Requer FINANCE_PG_CONCURRENCY_TEST_URL com acesso autorizado a um banco
LOCAL chamado exatamente finance_concurrency_test.
Sem a variável, ignora os testes sem estabelecer conexão.
Não cria tabelas, usuários ou bancos; não acessa o Supabase.
"""
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.services.budget_write_lock import (
    BUDGET_WRITE_LOCK_ID,
    acquire_budget_write_lock,
)

ENV_NAME = "FINANCE_PG_CONCURRENCY_TEST_URL"
TEST_DATABASE = "finance_concurrency_test"


def _engine():
    raw = os.environ.get(ENV_NAME)
    if not raw:
        pytest.skip("Conexão de testes não configurada; PostgreSQL não acessado.")
    try:
        url = make_url(raw)
    except Exception:
        pytest.fail("Conexão de testes inválida; valor não será exibido.")
    if not url.drivername.startswith("postgresql"):
        pytest.fail("É obrigatório utilizar PostgreSQL.")
    if (url.host or "").lower() not in ("localhost", "127.0.0.1", "::1"):
        pytest.fail("Conexões externas são proibidas neste teste.")
    if url.database != TEST_DATABASE:
        pytest.fail("Banco permitido exclusivamente: finance_concurrency_test.")
    return create_engine(
        url, poolclass=NullPool, connect_args={"connect_timeout": 3},
    )


def _other_session_can_lock(session: Session) -> bool:
    return bool(session.scalar(
        text("SELECT pg_try_advisory_xact_lock(:key)"),
        {"key": BUDGET_WRITE_LOCK_ID},
    ))


def test_budget_lock_blocks_second_session_until_commit():
    engine = _engine()
    try:
        with Session(engine) as first, Session(engine) as second:
            assert acquire_budget_write_lock(first) is True
            assert _other_session_can_lock(second) is False
            first.commit()
            assert _other_session_can_lock(second) is True
            second.rollback()
    finally:
        engine.dispose()


def test_budget_lock_released_after_rollback():
    engine = _engine()
    try:
        with Session(engine) as first, Session(engine) as second:
            assert acquire_budget_write_lock(first) is True
            assert _other_session_can_lock(second) is False
            first.rollback()
            assert _other_session_can_lock(second) is True
            second.rollback()
    finally:
        engine.dispose()
