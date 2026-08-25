from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.entity import Entity
from app.models.target_entry import TargetEntry
from app.repositories.target_repository import TargetRepository


def make_entity(db_session, code=7501):
    entity = Entity(codigo_entidade=code, nome=f"Entidade {code}")
    db_session.add(entity)
    db_session.commit()
    return entity


def make_target(entity, **overrides):
    values = {
        "entity_id": entity.id,
        "periodo_ano": 2026,
        "periodo_mes": 7,
        "indicador": "CONSULTAS",
        "valor_meta": Decimal("645495.9100"),
        "valor_realizado": Decimal("517670.6800"),
    }
    values.update(overrides)
    return TargetEntry(**values)


def test_valid_target_persists_decimal_and_entity(db_session):
    entity = make_entity(db_session)
    target = make_target(entity)
    db_session.add(target)
    db_session.commit()
    db_session.refresh(target)

    assert target.entity_id == entity.id
    assert target.valor_meta == Decimal("645495.9100")
    assert target.valor_realizado == Decimal("517670.6800")


@pytest.mark.parametrize(
    "overrides",
    [
        {"periodo_mes": 0},
        {"periodo_mes": 13},
        {"indicador": "INVALIDO"},
        {"valor_meta": Decimal("-1")},
        {"valor_realizado": Decimal("-1")},
    ],
)
def test_database_rejects_invalid_target(db_session, overrides):
    entity = make_entity(db_session)
    db_session.add(make_target(entity, **overrides))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_database_rejects_duplicate_functional_key(db_session):
    entity = make_entity(db_session)
    db_session.add(make_target(entity))
    db_session.commit()
    db_session.add(make_target(entity, valor_meta=Decimal("1")))

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_repository_queries_period_entity_and_year(db_session):
    first_entity = make_entity(db_session, 7501)
    second_entity = make_entity(db_session, 7503)
    repository = TargetRepository(db_session)
    first = repository.add(make_target(first_entity))
    second = repository.add(
        make_target(second_entity, indicador="REGISTROS", periodo_mes=8)
    )
    db_session.commit()

    assert repository.get_by_id(first.id) is first
    assert repository.exists(first_entity.id, 2026, 7, "CONSULTAS")
    assert repository.list_by_period(2026, 7) == [first]
    assert repository.list_by_entity(second_entity.id) == [second]
    assert repository.list_by_year(2026) == [first, second]
    assert repository.list_all() == [first, second]
