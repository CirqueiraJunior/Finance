"""Validação e preparação transacional da importação central de Metas."""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.importers.historical_parser import HistoricalWorkbookParser, TargetImportData
from app.models.target_entry import TargetEntry
from app.repositories.entity_repository import EntityRepository
from app.repositories.target_repository import TargetRepository


@dataclass(frozen=True, slots=True)
class TargetImportPreviewRow:
    line: int
    entity_id: int | None
    entity_code: int
    entity_name: str | None
    year: int
    month: int
    indicator: str
    target: Decimal
    actual: Decimal


@dataclass(frozen=True, slots=True)
class TargetImportValidation:
    file_name: str
    detected_type: str
    year: int | None
    sheets: tuple[str, ...]
    preview: tuple[TargetImportPreviewRow, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    target_total: Decimal
    actual_total: Decimal
    replacements: int = 0

    @property
    def can_import(self) -> bool:
        return bool(self.preview) and not self.errors


class TargetImportValidationError(ValueError):
    def __init__(self, validation: TargetImportValidation) -> None:
        super().__init__("A importação de Metas contém inconsistências bloqueantes.")
        self.validation = validation


class TargetImportService:
    def __init__(self, target_repository: TargetRepository,
                 entity_repository: EntityRepository,
                 parser: HistoricalWorkbookParser | None = None) -> None:
        if target_repository.session is not entity_repository.session:
            raise ValueError("Metas e Entidades devem compartilhar a mesma sessão.")
        self.targets = target_repository
        self.entities = entity_repository
        self.parser = parser or HistoricalWorkbookParser()

    def validate(self, file_path: str | Path, *, file_name: str | None = None
                 ) -> TargetImportValidation:
        result = self.parser.parse(file_path)
        errors = list(result.errors)
        warnings = list(result.warnings)
        if result.metadata.detected_type != "META_REALIZADO":
            errors.append("O arquivo selecionado não possui estrutura META_REALIZADO.")

        entities_by_code = {
            entity.codigo_entidade: entity
            for entity in self.entities.list_all()
            if entity.codigo_entidade != 7500
        }
        import_rows = [
            row for row in result.data if isinstance(row, TargetImportData)
        ]
        existing_keys = self.targets.existing_keys(row.year for row in import_rows)
        preview: list[TargetImportPreviewRow] = []
        seen: set[tuple[int, int, int, str]] = set()
        target_total = Decimal("0.0000")
        actual_total = Decimal("0.0000")
        replacements = 0
        for row in import_rows:
            entity = entities_by_code.get(row.code)
            key = (row.code, row.year, row.month, row.indicator)
            persisted_key = (
                entity.id, row.year, row.month, row.indicator
            ) if entity is not None else None
            if entity is None:
                if row.target == 0 and row.actual == 0:
                    warnings.append(
                        f"Linha {row.line}: Entidade {row.code} não cadastrada/inativa "
                        "ignorada porque Meta e Realizado estão zerados."
                    )
                    seen.add(key)
                    continue
                errors.append(
                    f"Linha {row.line}: Entidade {row.code} não cadastrada/inativa "
                    "possui valores e não pode ser ignorada."
                )
            elif key in seen:
                errors.append(
                    f"Linha {row.line}: registro repetido no arquivo para Entidade "
                    f"{row.code}, {row.month:02d}/{row.year}, {row.indicator}."
                )
            elif persisted_key in existing_keys:
                replacements += 1
            seen.add(key)
            preview.append(TargetImportPreviewRow(
                row.line, entity.id if entity else None, row.code,
                (entity.nome_oficial or entity.nome) if entity else None,
                row.year, row.month, row.indicator, row.target, row.actual,
            ))
            target_total += row.target
            actual_total += row.actual

        if replacements:
            warnings.append(
                f"{replacements} registro(s) existente(s) serão atualizado(s) "
                "pela reimportação."
            )

        if not preview and result.metadata.detected_type == "META_REALIZADO":
            errors.append("Nenhum registro de Meta válido foi encontrado no arquivo.")
        safe_name = Path(file_name or result.metadata.file_path.name).name
        return TargetImportValidation(
            safe_name, result.metadata.detected_type, result.metadata.year,
            result.metadata.sheets, tuple(preview), tuple(warnings),
            tuple(dict.fromkeys(errors)), target_total, actual_total,
            replacements,
        )

    def stage_import(self, file_path: str | Path, *, file_name: str | None = None
                     ) -> tuple[TargetImportValidation, tuple[TargetEntry, ...]]:
        validation = self.validate(file_path, file_name=file_name)
        if not validation.can_import:
            raise TargetImportValidationError(validation)
        entries: list[TargetEntry] = []
        new_entries: list[TargetEntry] = []

        try:
            for row in validation.preview:
                existing = self.targets.get_by_key(
                    row.entity_id,
                    row.year,
                    row.month,
                    row.indicator,
                )

                if existing is not None:
                    existing.valor_meta = row.target
                    existing.valor_realizado = row.actual
                    existing.observacao = (
                        f"Reimportação operacional: {validation.file_name}"
                    )
                    entries.append(existing)
                    continue

                entry = TargetEntry(
                    entity_id=row.entity_id,
                    periodo_ano=row.year,
                    periodo_mes=row.month,
                    indicador=row.indicator,
                    valor_meta=row.target,
                    valor_realizado=row.actual,
                    observacao=f"Importação operacional: {validation.file_name}",
                )
                new_entries.append(entry)
                entries.append(entry)

            self.targets.add_all(new_entries)
            self.targets.session.flush()

        except Exception:
            self.targets.session.rollback()
            raise

        return validation, tuple(entries)
