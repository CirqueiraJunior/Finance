from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.boe_entity_total import BOEEntityTotal
from app.models.entity import Entity
from app.repositories.boe_repository import BOERepository
from tests.boe_helpers import add_boe_import


def test_repository_finds_import_by_hash_and_period(db_session: Session) -> None:
    imported = add_boe_import(db_session, file_hash="e" * 64)
    repository = BOERepository(db_session)

    assert repository.get_import_by_hash("e" * 64) is imported
    assert repository.get_import_by_period(2026, 7) is imported
    assert repository.get_import_by_hash("f" * 64) is None


def test_repository_lists_imports_and_details(db_session: Session) -> None:
    older = add_boe_import(
        db_session, year=2026, month=6, file_hash="f" * 64, filename="junho.xlsx"
    )
    newer = add_boe_import(
        db_session, year=2026, month=7, file_hash="0" * 64, filename="julho.xlsx"
    )
    repository = BOERepository(db_session)

    assert repository.list_imports() == [newer, older]
    assert repository.get_import(newer.id) is newer


def test_repository_adds_and_lists_totals(db_session: Session) -> None:
    entity = Entity(codigo_entidade=7501, nome="CDL GOIANIA/GO")
    db_session.add(entity)
    db_session.commit()
    imported = add_boe_import(db_session, file_hash="1" * 64)
    repository = BOERepository(db_session)
    total = repository.add_entity_total(
        BOEEntityTotal(
            boe_import_id=imported.id,
            entity_id=entity.id,
            codigo_entidade_origem=7501,
            nome_entidade_origem=entity.nome,
            quantidade_consultas=10,
            valor_total=Decimal("0.6930"),
        )
    )
    db_session.commit()

    assert repository.list_totals_by_import(imported.id) == [total]

