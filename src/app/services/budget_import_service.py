"""Validação e preparação transacional da importação central de Orçamento."""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from app.importers.historical_parser import BudgetImportData, HistoricalWorkbookParser
from app.models.budget_entry import BudgetEntry
from app.repositories.budget_repository import BudgetRepository


@dataclass(frozen=True, slots=True)
class BudgetImportPreviewRow:
    line: int
    year: int
    month: int
    entry_type: str
    category: str
    value: Decimal
    source_label: str


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

        existing_keys = self.budgets.existing_keys(
            row.year for row in import_rows
        )

        preview: list[BudgetImportPreviewRow] = []
        seen: set[tuple[int, int, str, str]] = set()
        total = Decimal("0.0000")

        for row in import_rows:
            key = (row.year, row.month, row.entry_type, row.category)

            if key in seen:
                errors.append(
                    f"Linha {row.line}: registro repetido no arquivo para "
                    f"{row.month:02d}/{row.year}, {row.entry_type}, {row.category}."
                )
            elif key in existing_keys:
                errors.append(
                    f"Linha {row.line}: já existe Orçamento para "
                    f"{row.month:02d}/{row.year}, {row.entry_type}, {row.category}."
                )

            seen.add(key)

            preview.append(
                BudgetImportPreviewRow(
                    line=row.line,
                    year=row.year,
                    month=row.month,
                    entry_type=row.entry_type,
                    category=row.category,
                    value=row.value,
                    source_label=row.source_label,
                )
            )
            total += row.value

        if not preview and result.metadata.detected_type == "ORCAMENTO":
            errors.append(
                "Nenhum registro de Orçamento válido foi encontrado no arquivo."
            )

        safe_name = Path(
            file_name or result.metadata.file_path.name
        ).name

        return BudgetImportValidation(
            file_name=safe_name,
            detected_type=result.metadata.detected_type,
            year=result.metadata.year,
            sheets=result.metadata.sheets,
            preview=tuple(preview),
            warnings=tuple(warnings),
            errors=tuple(dict.fromkeys(errors)),
            total=total,
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
            for row in validation.preview:
                entries.append(
                    BudgetEntry(
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
                )

            self.budgets.add_all(entries)

        except Exception:
            self.budgets.session.rollback()
            raise

        return validation, tuple(entries)
