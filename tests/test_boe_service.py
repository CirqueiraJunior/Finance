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
        Entity(codigo_entidade=7501, nome="CDL GOIANIA/GO"),
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
