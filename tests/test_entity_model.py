import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entity import Entity
from app.models.entity_alias import EntityAlias


def test_create_and_persist_entity(db_session: Session) -> None:
    entity = Entity(codigo_entidade=1001, nome="CDL Goiânia")
    db_session.add(entity)
    db_session.commit()

    persisted = db_session.get(Entity, entity.id)

    assert persisted is not None
    assert persisted.codigo_entidade == 1001
    assert persisted.nome == "CDL Goiânia"
    assert persisted.ativa is True
    assert persisted.created_at is not None
    assert persisted.updated_at is not None


def test_entity_code_is_unique(db_session: Session) -> None:
    db_session.add_all(
        [
            Entity(codigo_entidade=1001, nome="Primeira"),
            Entity(codigo_entidade=1001, nome="Segunda"),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_entity_has_bidirectional_alias_relationship(db_session: Session) -> None:
    entity = Entity(codigo_entidade=1001, nome="Goiânia")
    entity.aliases.append(EntityAlias(alias="CDL GOIANIA/GO", origem="legado"))
    db_session.add(entity)
    db_session.commit()
    db_session.expire_all()

    persisted = db_session.get(Entity, entity.id)

    assert persisted is not None
    assert len(persisted.aliases) == 1
    assert persisted.aliases[0].alias == "CDL GOIANIA/GO"
    assert persisted.aliases[0].entity is persisted


def test_alias_is_unique_within_same_entity(db_session: Session) -> None:
    entity = Entity(codigo_entidade=1001, nome="Goiânia")
    entity.aliases.extend(
        [
            EntityAlias(alias="Goiânia"),
            EntityAlias(alias="Goiânia"),
        ]
    )
    db_session.add(entity)

    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

