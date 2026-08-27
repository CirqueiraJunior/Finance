import csv
from decimal import Decimal

import pytest

from app.core.exceptions import AssociationValidationError, CSVExportValidationError
from app.models.entity import Entity
from app.repositories.association_repository import AssociationRepository
from app.repositories.csv_export_repository import CSVExportRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.target_repository import TargetRepository
from app.services.association_service import AssociationService
from app.services.site_csv_service import (
    ASSOCIATION_HEADER,
    CSV_FILENAMES,
    TARGET_HEADER,
    SiteCSVService,
)
from app.services.target_service import TargetService


@pytest.fixture
def csv_context(db_session):
    entity = Entity(codigo_entidade=7501, nome="Goiânia", nome_oficial="CDL Goiânia")
    db_session.add(entity)
    db_session.commit()
    entity_repo = EntityRepository(db_session)
    target_repo = TargetRepository(db_session)
    association_repo = AssociationRepository(db_session)
    export_repo = CSVExportRepository(db_session)
    targets = TargetService(target_repo, entity_repo)
    associations = AssociationService(association_repo, entity_repo)
    csv_service = SiteCSVService(entity_repo, target_repo, association_repo, export_repo)
    return entity, targets, associations, csv_service


def test_association_service_validates_and_upserts(csv_context):
    entity, _, service, _ = csv_context
    entry = service.upsert(
        entity_id=entity.id,
        year=2026,
        month=7,
        capture_value="10.5000",
        execution_value="8.2500",
    )
    assert entry.valor_captacao == Decimal("10.5000")
    updated = service.upsert(
        entity_id=entity.id,
        year=2026,
        month=7,
        capture_value="12.0000",
        execution_value="9.0000",
    )
    assert updated.id == entry.id
    assert updated.valor_execucao == Decimal("9.0000")
    with pytest.raises(AssociationValidationError):
        service.upsert(
            entity_id=entity.id, year=2026, month=13,
            capture_value="1", execution_value="1",
        )
    with pytest.raises(AssociationValidationError):
        service.upsert(
            entity_id=entity.id, year=2026, month=8,
            capture_value=1.5, execution_value="1",
        )


def test_csv_validation_blocks_incomplete_year(csv_context, tmp_path):
    _, _, _, service = csv_context
    result = service.validate_year(2026)
    assert not result.valid
    assert any("Meta/Realizado ausente" in item for item in result.errors)
    assert any("Associação ausente" in item for item in result.errors)
    with pytest.raises(CSVExportValidationError):
        service.export_all(2026, tmp_path)
    assert service.list_history()[0].status == "FAILED"


def test_generates_five_official_csv_contracts(csv_context, tmp_path):
    entity, targets, associations, service = csv_context
    for month in range(1, 13):
        targets.create_target(
            entity_id=entity.id, year=2026, month=month, indicator="CONSULTAS",
            target_value=f"{month}.1000", actual_value=f"{month}.2000",
        )
        targets.create_target(
            entity_id=entity.id, year=2026, month=month, indicator="REGISTROS",
            target_value=f"{month}.3000", actual_value=f"{month}.4000",
        )
        associations.upsert(
            entity_id=entity.id, year=2026, month=month,
            capture_value=f"{month}.5000", execution_value=f"{month}.6000",
        )

    validation = service.validate_year(2026)
    assert validation.valid
    result = service.export_all(2026, tmp_path)
    assert tuple(path.name for path in result.files) == CSV_FILENAMES
    assert result.report_file.exists()

    with result.files[0].open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=";"))
    assert tuple(rows[0]) == ASSOCIATION_HEADER
    assert rows[1][0:4] == ["7501", "2026", "1,5000", "1,6000"]

    with result.files[1].open(encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle, delimiter=";"))
    assert tuple(rows[0]) == TARGET_HEADER
    assert rows[1][0:4] == ["7501", "2026", "1,1000", "2,1000"]

    history = service.list_history()
    assert history[0].status == "SUCCESS"
    assert "wp25_membros_associacao.csv" in history[0].arquivos
