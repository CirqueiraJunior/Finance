from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.budget_entry import BudgetEntry
from app.repositories.budget_repository import BudgetRepository


def make_budget(**overrides):
    values = dict(
        periodo_ano=2026, periodo_mes=7, tipo="DESPESA", categoria="SOFTWARE",
        valor_orcado=Decimal("2000.0000"), observacao="Teste",
    )
    values.update(overrides)
    return BudgetEntry(**values)


def test_valid_budget_persists_decimal(db_session):
    budget = make_budget()
    db_session.add(budget)
    db_session.commit()
    assert budget.valor_orcado == Decimal("2000.0000")


@pytest.mark.parametrize(
    "overrides",
    [
        {"periodo_mes": 13},
        {"periodo_ano": 1999},
        {"valor_orcado": Decimal("-1")},
        {"tipo": "RECEITA", "categoria": "SOFTWARE"},
    ],
)
def test_database_rejects_invalid_budget(db_session, overrides):
    db_session.add(make_budget(**overrides))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_database_rejects_duplicate_budget(db_session):
    db_session.add(make_budget())
    db_session.commit()
    db_session.add(make_budget(valor_orcado=Decimal("3000")))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_budget_repository_queries(db_session):
    repository = BudgetRepository(db_session)
    july = repository.add(make_budget())
    repository.add(make_budget(periodo_mes=8))
    db_session.commit()

    assert repository.get_by_id(july.id) is july
    assert repository.exists(2026, 7, "DESPESA", "SOFTWARE")
    assert repository.list_by_period(2026, 7) == [july]
    assert len(repository.list_by_year(2026)) == 2
    assert len(repository.list_all()) == 2
