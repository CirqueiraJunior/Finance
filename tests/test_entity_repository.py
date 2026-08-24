from sqlalchemy.orm import Session

from app.models.entity import Entity
from app.repositories.entity_repository import EntityRepository


def test_repository_add_and_get_by_id(db_session: Session) -> None:
    repository = EntityRepository(db_session)
    entity = repository.add(Entity(codigo_entidade=1002, nome="Anápolis"))
    db_session.commit()

    assert repository.get_by_id(entity.id) is entity


def test_repository_get_by_code(db_session: Session) -> None:
    repository = EntityRepository(db_session)
    repository.add(Entity(codigo_entidade=1003, nome="Aparecida de Goiânia"))
    db_session.commit()

    entity = repository.get_by_code(1003)

    assert entity is not None
    assert entity.nome == "Aparecida de Goiânia"


def test_repository_lists_entities_ordered_by_code(db_session: Session) -> None:
    repository = EntityRepository(db_session)
    repository.add(Entity(codigo_entidade=1005, nome="Quinta"))
    repository.add(Entity(codigo_entidade=1004, nome="Quarta"))
    db_session.commit()

    assert [item.codigo_entidade for item in repository.list_all()] == [1004, 1005]


def test_repository_checks_code_existence(db_session: Session) -> None:
    repository = EntityRepository(db_session)
    repository.add(Entity(codigo_entidade=1006, nome="Sexta"))
    db_session.commit()

    assert repository.exists_by_code(1006) is True
    assert repository.exists_by_code(9999) is False

