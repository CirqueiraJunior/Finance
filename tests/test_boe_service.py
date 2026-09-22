from decimal import Decimal

import pytest
from sqlalchemy import select

from app.core.exceptions import BOEValidationError
from app.importers.boe_importer import BOEImporter
from app.models.boe_entity_total import BOEEntityTotal
from app.models.boe_import import BOEImport
from app.models.entity import Entity
from app.repositories.boe_repository import BOERepository
from app.repositories.entity_repository import EntityRepository
from app.services.boe_service import BOEService
from tests.boe_helpers import add_boe_import, create_boe_workbook


@pytest.fixture
def boe_service(db_session):
    entities = [
        Entity(
            codigo_entidade=7501,
            nome="CDL GOIANIA/GO",
            nome_oficial="Câmara de Dirigentes Lojistas de Goiânia",
        ),
        Entity(codigo_entidade=7544, nome="CDL ANAPOLIS/GO"),
    ]
    db_session.add_all(entities)
    db_session.commit()
    return BOEService(
        BOERepository(db_session),
        EntityRepository(db_session),
        BOEImporter(),
    )


def test_validate_approved_file(boe_service, tmp_path):
    path = create_boe_workbook(tmp_path / "BOE - 07.26.xlsx")

    result = boe_service.validate_file(path)

    assert result.aprovado
    assert result.quantidade_erros == 0
    assert len(result.linhas) == 2


def test_validate_rejects_unknown_entity(boe_service, tmp_path):
    path = create_boe_workbook(
        tmp_path / "BOE - 07.26.xlsx",
        rows=[(9999, "ENTIDADE DESCONHECIDA", 1, Decimal("1.0000"))],
    )

    result = boe_service.validate_file(path)

    assert not result.aprovado
    assert "não encontrado" in result.inconsistencias[0].mensagem


def test_validate_warns_when_name_diverges(boe_service, tmp_path):
    path = create_boe_workbook(
        tmp_path / "BOE - 07.26.xlsx",
        rows=[(7501, "NOME DIVERGENTE", 1, Decimal("1.0000"))],
    )

    result = boe_service.validate_file(path)

    assert result.aprovado
    assert result.quantidade_avisos == 1


def test_validate_rejects_duplicate_hash(boe_service, tmp_path):
    path = create_boe_workbook(tmp_path / "BOE - 07.26.xlsx")
    parsed = boe_service.importer.parse(path)
    add_boe_import(
        boe_service.repository.session,
        year=2025,
        month=1,
        file_hash=parsed.hash_arquivo,
    )

    result = boe_service.validate_file(path)

    assert not result.aprovado
    assert any("arquivo BOE já foi importado" in item.mensagem for item in result.inconsistencias)


def test_validate_rejects_duplicate_period(boe_service, tmp_path):
    path = create_boe_workbook(tmp_path / "BOE - 07.26.xlsx")
    add_boe_import(boe_service.repository.session, file_hash="b" * 64)

    result = boe_service.validate_file(path)

    assert not result.aprovado
    assert any("para este período" in item.mensagem for item in result.inconsistencias)


def test_import_persists_header_totals_and_warning(boe_service, tmp_path):
    path = create_boe_workbook(
        tmp_path / "BOE - 07.26.xlsx",
        rows=[(7501, "NOME DIVERGENTE", 100, Decimal("6.9300"))],
    )

    imported = boe_service.import_file(path)

    assert imported.quantidade_entidades == 1
    assert imported.quantidade_inconsistencias == 1
    assert imported.valor_total == Decimal("6.9300")
    details = boe_service.get_import_details(imported.id)
    assert details is not None
    assert len(details.entity_totals) == 1
    assert len(details.issues) == 1


def test_detail_aggregates_rows_and_prefers_official_entity_name(
    boe_service, tmp_path
):
    path = create_boe_workbook(tmp_path / "BOE - 07.26.xlsx")
    imported = boe_service.import_file(path)

    details = boe_service.get_import_details(imported.id)

    assert details is not None
    assert [row.code for row in details.entities] == [7501, 7544]
    assert details.entities[0].entity_name == "Câmara de Dirigentes Lojistas de Goiânia"
    assert details.entities[0].source_name == "CDL GOIANIA/GO"
    assert details.total_entities == 2
    assert details.total_queries == 150
    assert details.total_value == Decimal("10.3950")
    assert isinstance(details.total_value, Decimal)


def test_detail_returns_none_for_unknown_import(boe_service):
    assert boe_service.get_import_details(999_999) is None


def test_detail_handles_import_without_entity_rows(boe_service):
    imported = add_boe_import(
        boe_service.repository.session,
        year=2026,
        month=8,
        file_hash="8" * 64,
    )

    details = boe_service.get_import_details(imported.id)

    assert details is not None
    assert details.entities == ()
    assert details.total_entities == 0
    assert details.total_queries == 0
    assert details.total_value == Decimal("0.0000")


def test_detail_defensively_excludes_consolidated_code_7500(boe_service):
    session = boe_service.repository.session
    consolidated = Entity(codigo_entidade=7500, nome="TOTAL CONSOLIDADO")
    session.add(consolidated)
    session.commit()
    imported = add_boe_import(
        session, year=2026, month=8, file_hash="7" * 64
    )
    session.add(
        BOEEntityTotal(
            boe_import_id=imported.id,
            entity_id=consolidated.id,
            codigo_entidade_origem=7500,
            nome_entidade_origem=consolidated.nome,
            quantidade_consultas=999,
            valor_total=Decimal("999.0000"),
        )
    )
    session.commit()

    details = boe_service.get_import_details(imported.id)

    assert details is not None
    assert details.entities == ()
    assert details.total_queries == 0
    assert details.total_value == Decimal("0.0000")


def test_import_rejects_invalid_file_without_persisting(boe_service, tmp_path):
    path = create_boe_workbook(
        tmp_path / "BOE - 07.26.xlsx",
        rows=[(9999, "ENTIDADE DESCONHECIDA", 1, Decimal("1.0000"))],
    )

    with pytest.raises(BOEValidationError):
        boe_service.import_file(path)

    assert boe_service.repository.session.scalars(select(BOEImport)).all() == []


def test_import_rolls_back_transaction_on_failure(boe_service, tmp_path, monkeypatch):
    path = create_boe_workbook(tmp_path / "BOE - 07.26.xlsx")

    def fail_on_total(_total: BOEEntityTotal) -> BOEEntityTotal:
        raise RuntimeError("falha controlada")

    monkeypatch.setattr(boe_service.repository, "add_entity_total", fail_on_total)

    with pytest.raises(RuntimeError, match="falha controlada"):
        boe_service.import_file(path)

    assert boe_service.repository.session.scalars(select(BOEImport)).all() == []


def test_operational_query_combines_period_and_entity_filters(boe_service):
    session = boe_service.repository.session
    first, second = session.scalars(select(Entity).order_by(Entity.codigo_entidade)).all()
    june = add_boe_import(session, year=2026, month=6, file_hash="3" * 64)
    july = add_boe_import(session, year=2026, month=7, file_hash="4" * 64)
    august = add_boe_import(session, year=2026, month=8, file_hash="5" * 64)
    session.add_all([
        BOEEntityTotal(boe_import_id=june.id, entity_id=first.id, codigo_entidade_origem=7501,
            nome_entidade_origem=first.nome, quantidade_consultas=10, valor_total=Decimal("1.0000")),
        BOEEntityTotal(boe_import_id=july.id, entity_id=first.id, codigo_entidade_origem=7501,
            nome_entidade_origem=first.nome, quantidade_consultas=20, valor_total=Decimal("4.0000")),
        BOEEntityTotal(boe_import_id=july.id, entity_id=second.id, codigo_entidade_origem=7544,
            nome_entidade_origem=second.nome, quantidade_consultas=40, valor_total=Decimal("8.0000")),
        BOEEntityTotal(boe_import_id=august.id, entity_id=first.id, codigo_entidade_origem=7501,
            nome_entidade_origem=first.nome, quantidade_consultas=80, valor_total=Decimal("16.0000")),
    ])
    session.commit()

    result = boe_service.query_operations(2026, 6, 2026, 7, first.id)

    assert [(row.month, row.entity_id) for row in result.rows] == [(6, first.id), (7, first.id)]
    assert result.total_queries == 30
    assert result.total_value == Decimal("5.0000")
    assert result.unit_value == Decimal("5.0000") / 30


def test_operational_query_filters_entity_and_calculates_all_kpis(boe_service):
    session = boe_service.repository.session
    first, second = session.scalars(select(Entity).order_by(Entity.codigo_entidade)).all()
    imported = add_boe_import(session, year=2025, month=12, file_hash="6" * 64)
    session.add_all([
        BOEEntityTotal(boe_import_id=imported.id, entity_id=first.id, codigo_entidade_origem=7501,
            nome_entidade_origem=first.nome, quantidade_consultas=25, valor_total=Decimal("5.0000")),
        BOEEntityTotal(boe_import_id=imported.id, entity_id=second.id, codigo_entidade_origem=7544,
            nome_entidade_origem=second.nome, quantidade_consultas=75, valor_total=Decimal("15.0000")),
    ])
    session.commit()

    all_entities = boe_service.query_operations(2025, 12, 2025, 12)
    only_second = boe_service.query_operations(2025, 12, 2025, 12, second.id)

    assert all_entities.total_queries == 100
    assert all_entities.total_value == Decimal("20.0000")
    assert all_entities.unit_value == Decimal("0.2000")
    assert [row.entity_id for row in only_second.rows] == [second.id]
    assert only_second.total_queries == 75
