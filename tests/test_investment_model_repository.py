from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.investment_movement import InvestmentMovement
from app.repositories.investment_repository import InvestmentRepository


def movement(**overrides):
    values = dict(
        data_movimento=date(2026, 7, 5), periodo_ano=2026, periodo_mes=7,
        tipo="APLICACAO", descricao="Aplicação", valor=Decimal("1000.0000"),
    )
    values.update(overrides)
    return InvestmentMovement(**values)


def test_valid_application_and_redemption_persist(db_session):
    repository = InvestmentRepository(db_session)
    application = repository.add(movement())
    redemption = repository.add(movement(
        data_movimento=date(2026, 7, 20), tipo="RESGATE", descricao="Resgate",
        valor=Decimal("250.0000"),
    ))
    db_session.commit()
    assert application.valor == Decimal("1000.0000")
    assert redemption.tipo == "RESGATE"
    assert repository.get_by_id(application.id) is application


@pytest.mark.parametrize("overrides", [
    {"tipo": "INVALIDO"}, {"valor": Decimal("0")},
    {"valor": Decimal("-1")}, {"periodo_mes": 13},
    {"periodo_ano": 1999}, {"descricao": "   "},
])
def test_database_rejects_invalid_movement(db_session, overrides):
    db_session.add(movement(**overrides))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_repository_lists_period_and_until_date(db_session):
    repository = InvestmentRepository(db_session)
    first = repository.add(movement())
    second = repository.add(movement(data_movimento=date(2026, 8, 1), periodo_mes=8))
    db_session.commit()
    assert repository.list_all() == [first, second]
    assert repository.list_by_period(2026, 7) == [first]
    assert repository.list_until_date(date(2026, 7, 31)) == [first]
