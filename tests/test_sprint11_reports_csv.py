import csv
from decimal import Decimal

import pytest
from PySide6.QtCore import Qt

from app.core.exceptions import AssociationValidationError, CSVExportValidationError
from app.gui.controllers.report_controller import ReportController
from app.gui.pages.relatorios import RelatoriosPage
from app.models.entity import Entity
from app.repositories.association_repository import AssociationRepository
from app.repositories.csv_export_repository import CSVExportRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.target_repository import TargetRepository
from app.services.association_service import AssociationService
from app.services.remote_services import RemoteCSVService
from app.services.report_service import AnnualReport
from app.services.site_csv_service import (
    ASSOCIATION_HEADER,
    CSVExportResult,
    CSV_FILENAMES,
    CSVValidationResult,
    TARGET_HEADER,
    SiteCSVService,
)
from app.services.target_service import TargetService


@pytest.fixture
def csv_context(db_session):
    first = Entity(codigo_entidade=7501, nome="Goiânia", nome_oficial="CDL Goiânia")
    second = Entity(codigo_entidade=7502, nome="Anápolis", nome_oficial="CDL Anápolis")
    fcdl = Entity(codigo_entidade=7600, nome="FCDL", nome_oficial="FCDL do Estado")
    db_session.add_all((first, second, fcdl))
    db_session.commit()
    entity_repo = EntityRepository(db_session)
    target_repo = TargetRepository(db_session)
    association_repo = AssociationRepository(db_session)
    export_repo = CSVExportRepository(db_session)
    return {
        "details": (first, second),
        "fcdl": fcdl,
        "targets": TargetService(target_repo, entity_repo),
        "associations": AssociationService(association_repo, entity_repo),
        "service": SiteCSVService(
            entity_repo, target_repo, association_repo, export_repo
        ),
        "session": db_session,
    }


def _seed_annual_data(context):
    targets = context["targets"]
    associations = context["associations"]
    for entity_index, entity in enumerate(context["details"], 1):
        for month in range(1, 13):
            targets.create_target(
                entity_id=entity.id, year=2026, month=month, indicator="CONSULTAS",
                target_value=str(entity_index * 100 + month),
                actual_value=str(entity_index * 10 + month),
            )
            targets.create_target(
                entity_id=entity.id, year=2026, month=month, indicator="REGISTROS",
                target_value=str(entity_index * 1000 + month),
                actual_value=str(entity_index * 100 + month),
            )
            if month <= 7:
                associations.upsert(
                    entity_id=entity.id, year=2026, month=month,
                    capture_value=str(entity_index + month),
                    execution_value=str(entity_index * 10 + month),
                )

    associations.upsert(
        entity_id=context["fcdl"].id, year=2026, month=1,
        capture_value="888888", execution_value="888888",
    )
    context["session"].commit()


def test_association_service_validates_and_upserts(csv_context):
    entity = csv_context["details"][0]
    service = csv_context["associations"]
    entry = service.upsert(
        entity_id=entity.id, year=2026, month=7,
        capture_value="10.5000", execution_value="8.2500",
    )
    assert entry.valor_captacao == Decimal("10.5000")
    updated = service.upsert(
        entity_id=entity.id, year=2026, month=7,
        capture_value="12.0000", execution_value="9.0000",
    )
    assert updated.id == entry.id
    assert updated.valor_execucao == Decimal("9.0000")
    with pytest.raises(AssociationValidationError):
        service.upsert(
            entity_id=entity.id, year=2026, month=13,
            capture_value="1", execution_value="1",
        )


def test_csv_validation_blocks_missing_annual_targets(csv_context, tmp_path):
    service = csv_context["service"]
    result = service.validate_period(2026)
    assert not result.valid
    assert any("Meta/Realizado ausente" in item for item in result.errors)
    assert not any("Associação ausente" in item for item in result.errors)
    with pytest.raises(CSVExportValidationError):
        service.export_all(2026, tmp_path)
    assert service.list_history()[0].status == "FAILED"


def test_generates_virtual_7500_without_registration_and_excludes_7600(
    csv_context, tmp_path,
):
    _seed_annual_data(csv_context)
    service = csv_context["service"]

    validation = service.validate_period(2026)
    assert validation.valid
    result = service.export_all(2026, tmp_path)
    assert tuple(path.name for path in result.files) == CSV_FILENAMES
    assert result.report_file.name == "relatorio_exportacao_2026.txt"

    with result.files[0].open(encoding="utf-8", newline="") as handle:
        association_rows = list(csv.reader(handle, delimiter=";"))
    assert tuple(association_rows[0]) == ASSOCIATION_HEADER
    assert len(association_rows[0]) == 26
    association_by_code = {row[0]: row for row in association_rows[1:]}
    assert set(association_by_code) == {"7500", "7501", "7502"}
    assert association_by_code["7500"][2:4] == ["5,0000", "32,0000"]
    assert association_by_code["7500"][16:] == ["0,0000"] * 10

    with result.files[1].open(encoding="utf-8", newline="") as handle:
        target_rows = list(csv.reader(handle, delimiter=";"))
    assert tuple(target_rows[0]) == TARGET_HEADER
    assert len(target_rows[0]) == 14
    target_by_code = {row[0]: row for row in target_rows[1:]}
    assert set(target_by_code) == {"7500", "7501", "7502"}
    assert target_by_code["7500"][2] == "302,0000"

    report = result.report_file.read_text(encoding="utf-8")
    assert "Ano: 2026" in report
    assert "Competência:" not in report


def test_report_gui_and_controller_use_only_year(qtbot, tmp_path):
    class Reports:
        def __init__(self):
            self.years = []

        def get_annual_report(self, year):
            self.years.append(year)
            return AnnualReport(year, ())

    class Exports:
        class Repository:
            class Session:
                def rollback(self):
                    pass
            session = Session()
        export_repository = Repository()

        def __init__(self):
            self.validations = []
            self.exports = []

        def validate_period(self, year):
            self.validations.append(year)
            return CSVValidationResult(year, True, (), 3, 48, 14)

        def export_all(self, year, destination):
            self.exports.append((year, destination))
            validation = CSVValidationResult(year, True, (), 3, 48, 14)
            return CSVExportResult(
                year, destination,
                tuple(destination / name for name in CSV_FILENAMES),
                destination / f"relatorio_exportacao_{year}.txt", validation,
            )

    page = RelatoriosPage()
    qtbot.addWidget(page)
    reports = Reports()
    exports = Exports()
    ReportController(page, reports, exports)
    reports.years.clear()
    page.year_filter.setValue(2026)

    assert not hasattr(page, "month_filter")
    assert not hasattr(page, "selected_month")
    qtbot.mouseClick(page.refresh_button, Qt.MouseButton.LeftButton)
    qtbot.mouseClick(page.validate_button, Qt.MouseButton.LeftButton)
    page._destination = tmp_path
    qtbot.mouseClick(page.export_button, Qt.MouseButton.LeftButton)

    assert reports.years == [2026]
    assert exports.validations == [2026]
    assert exports.exports == [(2026, tmp_path)]


def test_remote_csv_service_sends_only_year(tmp_path, monkeypatch):
    class API:
        def __init__(self):
            self.get_paths = []
            self.downloads = []

        def get(self, path):
            self.get_paths.append(path)
            return {
                "year": 2026, "valid": True, "errors": [], "entity_count": 3,
                "target_rows": 48, "association_rows": 14,
            }

        def download(self, path, payload):
            self.downloads.append((path, payload))
            import io
            from zipfile import ZipFile
            buffer = io.BytesIO()
            with ZipFile(buffer, "w") as archive:
                for name in CSV_FILENAMES:
                    archive.writestr(name, "")
                archive.writestr("relatorio_exportacao_2026.txt", "Ano: 2026")
            return buffer.getvalue()

    api = API()
    service = RemoteCSVService(api)
    service.validate_period(2026)
    service.export_all(2026, tmp_path)

    assert api.get_paths == [
        "/api/v1/reports/csv-validation?year=2026",
        "/api/v1/reports/csv-validation?year=2026",
    ]
    assert api.downloads == [
        ("/api/v1/reports/csv-export", {"year": 2026})
    ]
