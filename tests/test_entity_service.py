import pytest
from sqlalchemy.orm import Session

from app.core.exceptions import (
    EntityAliasAlreadyExistsError,
    EntityCodeAlreadyExistsError,
    InvalidEntityCodeError,
)
from app.repositories.entity_repository import EntityRepository
from app.services.entity_service import EntityService


@pytest.fixture
def entity_service(db_session: Session) -> EntityService:
    return EntityService(EntityRepository(db_session))


def test_service_creates_valid_entity(entity_service: EntityService) -> None:
    entity = entity_service.create_entity(
        codigo_entidade=2001,
        nome="  CDL Goiânia  ",
        municipio=" Goiânia ",
        uf="go",
    )

    assert entity.id is not None
    assert entity.nome == "CDL Goiânia"
    assert entity.municipio == "Goiânia"
    assert entity.uf == "GO"


def test_service_rejects_consolidated_code(entity_service: EntityService) -> None:
    with pytest.raises(
        InvalidEntityCodeError,
        match="O código 7500 representa o consolidado geral",
    ):
        entity_service.create_entity(codigo_entidade=7500, nome="Consolidado")


def test_service_rejects_duplicate_code(entity_service: EntityService) -> None:
    entity_service.create_entity(codigo_entidade=2002, nome="Original")

    with pytest.raises(EntityCodeAlreadyExistsError):
        entity_service.create_entity(codigo_entidade=2002, nome="Duplicada")


def test_service_adds_alias(entity_service: EntityService) -> None:
    entity = entity_service.create_entity(codigo_entidade=2003, nome="Goiânia")

    entity_alias = entity_service.add_alias(
        entity,
        " CDL GOIANIA/GO ",
        origem=" BOE ",
    )

    assert entity_alias.id is not None
    assert entity_alias.alias == "CDL GOIANIA/GO"
    assert entity_alias.origem == "BOE"
    assert entity_alias.entity_id == entity.id


def test_service_rejects_duplicate_alias(entity_service: EntityService) -> None:
    entity = entity_service.create_entity(codigo_entidade=2004, nome="Goiânia")
    entity_service.add_alias(entity, "Goiânia")

    with pytest.raises(EntityAliasAlreadyExistsError):
        entity_service.add_alias(entity, "Goiânia")


def test_service_gets_entity_by_code(entity_service: EntityService) -> None:
    created = entity_service.create_entity(codigo_entidade=2005, nome="Anápolis")

    found = entity_service.get_entity_by_code(2005)

    assert found is not None
    assert found.id == created.id


def test_service_lists_entities(entity_service: EntityService) -> None:
    entity_service.create_entity(codigo_entidade=2007, nome="Sétima")
    entity_service.create_entity(codigo_entidade=2006, nome="Sexta")

    assert [item.codigo_entidade for item in entity_service.list_entities()] == [
        2006,
        2007,
    ]

