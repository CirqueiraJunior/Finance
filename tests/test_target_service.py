from decimal import Decimal

import pytest

from app.core.exceptions import TargetDuplicateError, TargetValidationError
from app.models.entity import Entity
from app.repositories.entity_repository import EntityRepository
from app.repositories.target_repository import TargetRepository
from app.services.target_service import TargetService


@pytest.fixture
def target_context(db_session):
    active = Entity(
        codigo_entidade=7501,
        nome="Goiânia",
        nome_oficial="CDL Goiânia",
    )
    second = Entity(codigo_entidade=7503, nome="Valparaíso de Goiás")
    consolidated = Entity(codigo_entidade=7500, nome="Consolidado")
    inactive = Entity(codigo_entidade=9998, nome="Inativa", ativa=False)
    db_session.add_all([active, second, consolidated, inactive])
    db_session.commit()
    service = TargetService(
        TargetRepository(db_session), EntityRepository(db_session)
    )
    return service, active, second, consolidated, inactive


def test_create_update_and_queries(target_context):
    service, entity, *_ = target_context
    target = service.create_target(
        entity_id=entity.id,
        year=2026,
        month=7,
        indicator="CONSULTAS",
        target_value="645495.9100",
        actual_value="517670.6800",
        notes="Planilha oficial",
    )

    assert target.valor_meta == Decimal("645495.9100")
    assert target.valor_realizado == Decimal("517670.6800")
    assert service.get_target(target.id) is target
    assert service.list_by_period(2026, 7) == [target]
    assert service.list_by_entity(entity.id) == [target]
    assert service.list_by_year(2026) == [target]

    updated = service.update_target(
        target.id, target_value="650000.0000", notes="Revisada"
    )
    assert updated.valor_meta == Decimal("650000.0000")
    assert updated.valor_realizado == Decimal("517670.6800")
    assert updated.observacao == "Revisada"


def test_comparison_difference_achievement_and_summary(target_context):
    service, first, second, *_ = target_context
    service.create_target(
        entity_id=first.id, year=2026, month=7, indicator="CONSULTAS",
        target_value="100.0000", actual_value="80.0000",
    )
    service.create_target(
        entity_id=second.id, year=2026, month=7, indicator="CONSULTAS",
        target_value="50.0000", actual_value="75.0000",
    )

    result = service.get_target_vs_actual(2026, 7, "CONSULTAS")

    assert result.comparisons[0].difference == Decimal("-20.0000")
    assert result.comparisons[0].achievement_percentage == Decimal("80.0000")
    assert result.summary.entity_count == 2
    assert result.summary.target_total == Decimal("150.0000")
    assert result.summary.actual_total == Decimal("155.0000")
    assert result.summary.difference_total == Decimal("5.0000")
    assert result.summary.achievement_percentage == Decimal("103.3333")
    assert isinstance(result.summary.target_total, Decimal)


def test_zero_target_has_no_achievement(target_context):
    service, entity, *_ = target_context
    service.create_target(
        entity_id=entity.id, year=2026, month=7, indicator="REGISTROS",
        target_value="0", actual_value="10",
    )

    result = service.get_target_vs_actual(2026, 7, "REGISTROS")

    assert result.comparisons[0].achievement_percentage is None
    assert result.summary.achievement_percentage is None


def test_duplicate_unknown_entity_consolidated_and_invalid_inputs(target_context):
    service, entity, _, consolidated, inactive = target_context
    service.create_target(
        entity_id=entity.id, year=2026, month=7, indicator="CONSULTAS",
        target_value="1", actual_value="1",
    )
    with pytest.raises(TargetDuplicateError):
        service.create_target(
            entity_id=entity.id, year=2026, month=7, indicator="CONSULTAS",
            target_value="2", actual_value="2",
        )
    for entity_id in (999999, consolidated.id):
        with pytest.raises(TargetValidationError):
            service.create_target(
                entity_id=entity_id, year=2026, month=7, indicator="REGISTROS",
                target_value="1", actual_value="1",
            )

    target_inactive = service.create_target(
        entity_id=inactive.id, year=2026, month=7, indicator="REGISTROS",
        target_value="1", actual_value="1",
    )
    assert target_inactive.entity_id == inactive.id
    for kwargs in (
        {"month": 13},
        {"indicator": "INVALIDO"},
        {"target_value": "-1"},
        {"actual_value": "-1"},
        {"target_value": 1.5},
        {"actual_value": 1.5},
    ):
        values = {
            "entity_id": entity.id, "year": 2026, "month": 8,
            "indicator": "CONSULTAS", "target_value": "1", "actual_value": "1",
        }
        values.update(kwargs)
        with pytest.raises(TargetValidationError):
            service.create_target(**values)


def test_entity_lists_exclude_only_7500(target_context):
    service, active, second, consolidated, inactive = target_context
    entities = service.list_entities()
    assert entities == [active, second, inactive]
    assert consolidated not in entities
