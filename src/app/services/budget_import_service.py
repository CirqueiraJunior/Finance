"""Validação e preparação transacional da importação central de Orçamento."""

from dataclasses import dataclass, replace
from decimal import Decimal
from pathlib import Path

from app.importers.historical_parser import BudgetImportData, HistoricalWorkbookParser
from app.models.budget_entry import BudgetEntry
from app.repositories.budget_repository import BudgetRepository
from app.services.budget_import_snapshot import budget_snapshot


@dataclass(frozen=True, slots=True)
class BudgetImportPreviewRow:
    line: int
    year: int
    month: int
    entry_type: str
    category: str
    value: Decimal
    source_label: str
    status: str = 'NEW'
    previous_value: Decimal | None = None
    difference: Decimal = Decimal('0.0000')


@dataclass(frozen=True, slots=True)
class BudgetImportValidation:
    file_name: str
    detected_type: str
    year: int | None
    sheets: tuple[str, ...]
    preview: tuple[BudgetImportPreviewRow, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    total: Decimal
    replacements: int = 0
    new_count: int = 0
    changed_count: int = 0
    unchanged_count: int = 0
    snapshot_hash: str | None = None

    @property
    def can_import(self) -> bool:
        return bool(self.preview) and not self.errors


class BudgetImportValidationError(ValueError):
    def __init__(self, validation: BudgetImportValidation) -> None:
        super().__init__(
            "A importação de Orçamento contém inconsistências bloqueantes."
        )
        self.validation = validation


class BudgetImportService:
    def __init__(
        self,
        budget_repository: BudgetRepository,
        parser: HistoricalWorkbookParser | None = None,
    ) -> None:
        self.budgets = budget_repository
        self.parser = parser or HistoricalWorkbookParser()

    def validate(
        self,
        file_path: str | Path,
        *,
        file_name: str | None = None,
    ) -> BudgetImportValidation:
        result = self.parser.parse(file_path)

        errors = list(result.errors)
        warnings = list(result.warnings)

        if result.metadata.detected_type != "ORCAMENTO":
            errors.append(
                "O arquivo selecionado não possui estrutura de Orçamento reconhecida."
            )

        import_rows = [
            row for row in result.data if isinstance(row, BudgetImportData)
        ]

        # Aggregate only rows inside this uploaded workbook.
        # Do not add values previously stored in the database.
        grouped = {}
        skipped_zero = 0
        for row in import_rows:
            label = (row.source_label or "").strip()
            if not label or len(label) > 255:
                errors.append(
                    f"Linha {row.line}: descricao obrigatoria "
                    "com ate 255 caracteres."
                )
                continue
            if row.entry_type == "DESPESA" and row.value == 0:
                skipped_zero += 1
                continue
            key = (
                row.year, row.month, row.entry_type, row.category,
                self.budgets.description_key(label),
            )
            if key in grouped:
                first = grouped[key]
                grouped[key] = replace(
                    first, value=first.value + row.value
                )
            else:
                grouped[key] = replace(row, source_label=label)

        if skipped_zero:
            warnings.append(
                f"{skipped_zero} despesas zeradas ignoradas."
            )

        import_rows = list(grouped.values())
        requested_keys = set(grouped)

        groups = {
            (year, month, entry_type, category)
            for year, month, entry_type, category, _ in requested_keys
        }
        scoped_entries = self.budgets.by_groups(groups)
        existing_entries = {}
        for entry in scoped_entries:
            key = (
                entry.periodo_ano,
                entry.periodo_mes,
                entry.tipo,
                entry.categoria,
                self.budgets.description_key(entry.descricao),
            )
            if key in existing_entries:
                errors.append(
                    "Registros duplicados encontrados no or?amento existente."
                )
            elif key in requested_keys:
                existing_entries[key] = entry

        preview: list[BudgetImportPreviewRow] = []
        total = Decimal("0.0000")
        replacements = 0
        new_count = changed_count = unchanged_count = 0

        for row in import_rows:
            key = (
                row.year, row.month, row.entry_type, row.category,
                self.budgets.description_key(row.source_label),
            )
            existing = existing_entries.get(key)
            previous = Decimal(existing.valor_orcado) if existing is not None else None
            if existing is None:
                status = "NEW"
                new_count += 1
            else:
                replacements += 1
                same_value = previous == row.value
                same_description = (existing.descricao or "") == row.source_label
                status = "UNCHANGED" if same_value and same_description else "CHANGED"
                if status == "UNCHANGED":
                    unchanged_count += 1
                else:
                    changed_count += 1

            preview.append(
                BudgetImportPreviewRow(
                    line=row.line,
                    year=row.year,
                    month=row.month,
                    entry_type=row.entry_type,
                    category=row.category,
                    value=row.value,
                    source_label=row.source_label,
                    status=status,
                    previous_value=previous,
                    difference=row.value - (previous or Decimal("0")),
                )
            )
            total += row.value

        if not preview and result.metadata.detected_type == "ORCAMENTO":
            errors.append(
                "Nenhum registro de Orçamento válido foi encontrado no arquivo."
            )
        if changed_count:
            warnings.append(
                f"{changed_count} registros existentes apresentam diferenças "
                "de valor ou descrição."
            )

        safe_name = Path(
            file_name or result.metadata.file_path.name
        ).name

        validation = BudgetImportValidation(
            file_name=safe_name,
            detected_type=result.metadata.detected_type,
            year=result.metadata.year,
            sheets=result.metadata.sheets,
            preview=tuple(preview),
            warnings=tuple(warnings),
            errors=tuple(dict.fromkeys(errors)),
            total=total,
            replacements=replacements,
            new_count=new_count,
            changed_count=changed_count,
            unchanged_count=unchanged_count,
        )
        return replace(
            validation,
            snapshot_hash=budget_snapshot(
                validation, existing_entries, scoped_entries
            ),
        )

    def stage_import(
        self,
        file_path: str | Path,
        *,
        file_name: str | None = None,
    ) -> tuple[BudgetImportValidation, tuple[BudgetEntry, ...]]:
        validation = self.validate(file_path, file_name=file_name)

        if not validation.can_import:
            raise BudgetImportValidationError(validation)

        entries: list[BudgetEntry] = []

        try:
            keys = {
                (
                    row.year, row.month, row.entry_type, row.category,
                    self.budgets.description_key(row.source_label),
                )
                for row in validation.preview
            }
            existing = self.budgets.by_keys(keys)
            new_entries: list[BudgetEntry] = []
            for row in validation.preview:
                key = (
                    row.year, row.month, row.entry_type, row.category,
                    self.budgets.description_key(row.source_label),
                )
                entry = existing.get(key)
                if entry is None:
                    entry = BudgetEntry(
                        periodo_ano=row.year,
                        periodo_mes=row.month,
                        tipo=row.entry_type,
                        categoria=row.category,
                        descricao=row.source_label or None,
                        valor_orcado=row.value,
                        observacao=(
                            f"Importação operacional: {validation.file_name}"
                        ),
                    )
                    new_entries.append(entry)
                else:
                    entry.descricao = row.source_label or None
                    entry.valor_orcado = row.value
                    entry.observacao = (
                        f"Importação operacional: {validation.file_name}"
                    )
                entries.append(entry)

            self.budgets.add_all(new_entries)

        except Exception:
            self.budgets.session.rollback()
            raise

        return validation, tuple(entries)
