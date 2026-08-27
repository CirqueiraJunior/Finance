from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.core.exceptions import CSVExportValidationError
from app.models.csv_export import CSVExport
from app.models.target_entry import TargetIndicator
from app.repositories.association_repository import AssociationRepository
from app.repositories.csv_export_repository import CSVExportRepository
from app.repositories.entity_repository import EntityRepository
from app.repositories.target_repository import TargetRepository


MONTHS = ("JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ")
TARGET_HEADER = ("COD.", "ANO", *MONTHS)
ASSOCIATION_HEADER = (
    "COD", "ANO",
    *tuple(part for month in MONTHS for part in (f"{month} CAP", f"{month} EXEC")),
)
CSV_FILENAMES = (
    "wp25_membros_associacao.csv",
    "wp25_membros_consultas_metas.csv",
    "wp25_membros_consultas_realizadas.csv",
    "wp25_membros_registros_metas.csv",
    "wp25_membros_registros_realizados.csv",
)


@dataclass(frozen=True, slots=True)
class CSVValidationResult:
    valid: bool
    errors: tuple[str, ...]
    entity_count: int
    target_rows: int
    association_rows: int


@dataclass(frozen=True, slots=True)
class CSVExportResult:
    year: int
    directory: Path
    files: tuple[Path, ...]
    report_file: Path
    validation: CSVValidationResult


class SiteCSVService:
    """Generates the five CESPC/GO site CSV contracts from persisted data."""

    def __init__(
        self,
        entity_repository: EntityRepository,
        target_repository: TargetRepository,
        association_repository: AssociationRepository,
        export_repository: CSVExportRepository,
    ) -> None:
        sessions = {
            id(entity_repository.session),
            id(target_repository.session),
            id(association_repository.session),
            id(export_repository.session),
        }
        if len(sessions) != 1:
            raise ValueError("Exportação CSV deve compartilhar a mesma sessão.")
        self.entity_repository = entity_repository
        self.target_repository = target_repository
        self.association_repository = association_repository
        self.export_repository = export_repository

    def validate_year(self, year: int) -> CSVValidationResult:
        year = self._year(year)
        entities = [
            entity
            for entity in self.entity_repository.list_all()
            if entity.ativa and entity.codigo_entidade != 7500
        ]
        errors: list[str] = []
        codes = [entity.codigo_entidade for entity in entities]
        if not entities:
            errors.append("Nenhuma Entidade ativa disponível para exportação.")
        if len(codes) != len(set(codes)):
            errors.append("Existem códigos de Entidade duplicados.")

        targets = self.target_repository.list_by_year(year)
        target_map = {
            (item.entity_id, item.periodo_mes, item.indicador): item
            for item in targets
            if item.entity.codigo_entidade != 7500 and item.entity.ativa
        }
        associations = self.association_repository.list_by_year(year)
        association_map = {
            (item.entity_id, item.periodo_mes): item
            for item in associations
            if item.entity.codigo_entidade != 7500 and item.entity.ativa
        }

        for entity in entities:
            for month in range(1, 13):
                for indicator in (
                    TargetIndicator.QUERIES.value,
                    TargetIndicator.REGISTRATIONS.value,
                ):
                    if (entity.id, month, indicator) not in target_map:
                        errors.append(
                            f"Meta/Realizado ausente: {entity.codigo_entidade} "
                            f"{year}-{month:02d} {indicator}."
                        )
                if (entity.id, month) not in association_map:
                    errors.append(
                        f"Associação ausente: {entity.codigo_entidade} {year}-{month:02d}."
                    )

        return CSVValidationResult(
            valid=not errors,
            errors=tuple(errors),
            entity_count=len(entities),
            target_rows=len(targets),
            association_rows=len(associations),
        )

    def export_all(self, year: int, destination: str | Path) -> CSVExportResult:
        year = self._year(year)
        destination = Path(destination).expanduser().resolve()
        validation = self.validate_year(year)
        if not validation.valid:
            self._record(
                year,
                destination,
                "FAILED",
                (),
                self._validation_report(validation),
            )
            raise CSVExportValidationError(validation.errors)

        destination.mkdir(parents=True, exist_ok=True)
        entities = [
            entity
            for entity in self.entity_repository.list_all()
            if entity.ativa and entity.codigo_entidade != 7500
        ]
        targets = self.target_repository.list_by_year(year)
        target_map = {
            (item.entity_id, item.periodo_mes, item.indicador): item
            for item in targets
            if item.entity.codigo_entidade != 7500 and item.entity.ativa
        }
        associations = self.association_repository.list_by_year(year)
        association_map = {
            (item.entity_id, item.periodo_mes): item
            for item in associations
            if item.entity.codigo_entidade != 7500 and item.entity.ativa
        }

        created: list[Path] = []
        association_file = destination / CSV_FILENAMES[0]
        self._write_association(
            association_file, year, entities, association_map
        )
        created.append(association_file)

        definitions = (
            (CSV_FILENAMES[1], TargetIndicator.QUERIES.value, "valor_meta"),
            (CSV_FILENAMES[2], TargetIndicator.QUERIES.value, "valor_realizado"),
            (CSV_FILENAMES[3], TargetIndicator.REGISTRATIONS.value, "valor_meta"),
            (CSV_FILENAMES[4], TargetIndicator.REGISTRATIONS.value, "valor_realizado"),
        )
        for filename, indicator, attribute in definitions:
            path = destination / filename
            self._write_target(path, year, entities, target_map, indicator, attribute)
            created.append(path)

        report_file = destination / f"relatorio_exportacao_{year}.txt"
        report = self._success_report(year, created, validation)
        report_file.write_text(report, encoding="utf-8")
        self._record(year, destination, "SUCCESS", created, report)
        return CSVExportResult(
            year=year,
            directory=destination,
            files=tuple(created),
            report_file=report_file,
            validation=validation,
        )

    def list_history(self, limit: int = 20) -> list[CSVExport]:
        return self.export_repository.list_recent(limit)

    def _record(
        self,
        year: int,
        destination: Path,
        status: str,
        files: tuple[Path, ...] | list[Path],
        report: str,
    ) -> None:
        record = CSVExport(
            ano=year,
            status=status,
            diretorio=str(destination),
            arquivos="\n".join(path.name for path in files) or None,
            relatorio=report,
        )
        self.export_repository.add(record)
        self.export_repository.session.commit()

    @staticmethod
    def _write_target(path, year, entities, data, indicator, attribute) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter=";", lineterminator="\n")
            writer.writerow(TARGET_HEADER)
            for entity in entities:
                row = [entity.codigo_entidade, year]
                for month in range(1, 13):
                    item = data[(entity.id, month, indicator)]
                    row.append(SiteCSVService._decimal(getattr(item, attribute)))
                writer.writerow(row)

    @staticmethod
    def _write_association(path, year, entities, data) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter=";", lineterminator="\n")
            writer.writerow(ASSOCIATION_HEADER)
            for entity in entities:
                row = [entity.codigo_entidade, year]
                for month in range(1, 13):
                    item = data[(entity.id, month)]
                    row.extend(
                        (
                            SiteCSVService._decimal(item.valor_captacao),
                            SiteCSVService._decimal(item.valor_execucao),
                        )
                    )
                writer.writerow(row)

    @staticmethod
    def _decimal(value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.0001')):.4f}".replace(".", ",")

    @staticmethod
    def _validation_report(result: CSVValidationResult) -> str:
        lines = [
            "J.A. Finance - Validação de Exportação CSV",
            f"Status: {'APROVADO' if result.valid else 'BLOQUEADO'}",
            f"Entidades: {result.entity_count}",
            f"Registros Meta/Realizado: {result.target_rows}",
            f"Registros Associação: {result.association_rows}",
        ]
        if result.errors:
            lines.extend(["", "Inconsistências:", *result.errors])
        return "\n".join(lines)

    @staticmethod
    def _success_report(year: int, files: list[Path], validation: CSVValidationResult) -> str:
        return "\n".join(
            [
                "J.A. Finance - Relatório de Exportação CSV",
                "Status: SUCESSO",
                f"Ano: {year}",
                f"Entidades: {validation.entity_count}",
                "",
                "Arquivos:",
                *(path.name for path in files),
            ]
        )

    @staticmethod
    def _year(value: int) -> int:
        try:
            year = int(value)
        except (TypeError, ValueError) as error:
            raise CSVExportValidationError(("Ano inválido.",)) from error
        if not 2000 <= year <= 9999:
            raise CSVExportValidationError(("Ano inválido.",))
        return year
