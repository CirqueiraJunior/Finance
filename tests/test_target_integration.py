from decimal import Decimal

from app.models.entity import Entity
from app.repositories.entity_repository import EntityRepository
from app.repositories.target_repository import TargetRepository
from app.services.target_service import TargetService


def test_official_july_goiania_queries_scenario(db_session):
    entity = Entity(codigo_entidade=7501, nome="Goiânia")
    db_session.add(entity)
    db_session.commit()
    service = TargetService(
        TargetRepository(db_session), EntityRepository(db_session)
    )
    service.create_target(
        entity_id=entity.id,
        year=2026,
        month=7,
        indicator="CONSULTAS",
        target_value=Decimal("645495.9100"),
        actual_value=Decimal("517670.6800"),
    )

    comparison = service.get_target_vs_actual(
        2026, 7, "CONSULTAS"
    ).comparisons[0]

    assert comparison.target == Decimal("645495.9100")
    assert comparison.actual == Decimal("517670.6800")
    assert comparison.difference == Decimal("-127825.2300")
    assert comparison.achievement_percentage == Decimal("80.1974")
