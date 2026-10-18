"""Bloqueio transacional cooperativo para escritas de orçamento no PostgreSQL.

Todos os caminhos que alteram BudgetEntry devem chamar acquire_budget_write_lock
ANTES de ler/validar o estado e dentro da MESMA transação da gravação.
"""
from sqlalchemy import text
from sqlalchemy.orm import Session

# Identificador fixo e exclusivo para o domínio de Orçamento do Finance.
# Bloqueia também inserções de chaves ainda inexistentes, desde que o
# escritor utilize o mesmo bloqueio.
BUDGET_WRITE_LOCK_ID = 0x4A415F4255444745


def acquire_budget_write_lock(session: Session) -> bool:
    """Adquire bloqueio PostgreSQL até COMMIT/ROLLBACK; SQLite não o suporta.

    Retorna True quando adquirido; False para SQLite de testes.
    Outros bancos são recusados para impedir uma falsa garantia de segurança.
    """
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": BUDGET_WRITE_LOCK_ID},
        )
        return True
    if dialect == "sqlite":
        return False
    raise RuntimeError(f"Bloqueio de Orçamento indisponível para banco: {dialect}")
