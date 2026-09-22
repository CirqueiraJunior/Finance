"""Validação e preparação transacional da importação Financeiro."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.importers.historical_importer import HistoricalWorkbookImporter, normalized
from app.models.boe_import import BOEImport
from app.models.cashflow_entry import CashflowEntry
from app.models.financial_balance_entry import FinancialBalanceEntry
from app.models.investment_movement import InvestmentMovement
from app.services.cashflow_catalog_service import CashflowCatalogService


CATEGORY_MAP = {
    "RECEITA DIRETA": "RECEITA_DIRETA",
    "RECEITA INDIRETA": "RECEITA_INDIRETA",
    "ADMINISTRATIVO": "ADMINISTRATIVO",
    "DIRETORIA": "DIRETORIA",
    "EVENTOS": "EVENTOS",
    "OPERACIONAL": "OPERACIONAL",
    "PESSOAL": "PESSOAL",
    "INVESTIMENTO": "INVESTIMENTO",
    "RESGATE": "RESGATE",
    "OUTROS": "OUTROS",
    "SALDO APLICADO": "SALDO_APLICADO",
}
TYPE_MAP = {
    "RECEITA": "RECEITA",
    "DESPESA": "DESPESA",
    "APLICACAO": "APLICACAO",
    "RESGATE": "RESGATE",
    "SALDO": "SALDO",
}


@dataclass(frozen=True, slots=True)
class FinancialImportValidation:
    file_name: str
    detected_type: str
    preview: tuple[dict, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]
    duplicates: int
    total: Decimal

    @property
    def can_import(self) -> bool:
        return any(
            not row.get("duplicate") and not row.get("skip")
            for row in self.preview
        ) and not self.errors


class FinancialImportValidationError(ValueError):
    def __init__(self, validation: FinancialImportValidation) -> None:
        super().__init__(
            "A importação Financeiro contém inconsistências bloqueantes."
        )
        self.validation = validation


class FinancialImportService:
    """Mantém parse, validação e persistência da planilha em uma unidade."""

    def __init__(
        self,
        session: Session,
        catalog: CashflowCatalogService,
        importer: HistoricalWorkbookImporter | None = None,
    ) -> None:
        self.session = session
        self.catalog = catalog
        self.importer = importer or HistoricalWorkbookImporter()

    def validate(
        self, file_path: str | Path, *, file_name: str | None = None
    ) -> FinancialImportValidation:
        source = self.importer.parse(file_path)
        rows = [dict(row) for row in source.rows]
        warnings = list(source.warnings)
        errors = list(source.errors)

        if source.detected_type != "FLUXO_CAIXA":
            errors.append(
                "O arquivo selecionado não possui a estrutura Financeiro reconhecida."
            )

        official = {
            (normalized(item.descricao), item.categoria, item.tipo)
            for item in self.catalog.list_entries()
            if item.ativa
        }
        seen: set[tuple] = set()
        duplicates = 0

        for row in rows:
            if row.get("balance_type"):
                key = (
                    "SALDO", row["year"], row["month"], row["balance_type"]
                )
            else:
                category = CATEGORY_MAP.get(normalized(row.get("category_label")))
                kind = TYPE_MAP.get(normalized(row.get("type_label")))
                row["category"], row["type"] = category, kind
                if category is None or kind is None:
                    errors.append(
                        f"Linha {row['line']}: Categoria ou Tipo inválido."
                    )
                    continue
                if (normalized(row["description"]), category, kind) not in official:
                    errors.append(
                        f"Linha {row['line']}: combinação não encontrada no catálogo oficial."
                    )
                    continue
                if category == "RECEITA_DIRETA":
                    if self._is_january_2026_historical_direct(row):
                        warnings.append(
                            "Receita Direta de 01/2026 importada da base histórica "
                            "por ausência de BOE 12/2025."
                        )
                    else:
                        row["skip"] = True
                        warnings.append(
                            f"Linha {row['line']}: Receita Direta não será importada; "
                            "ela é gerada exclusivamente pelo BOE do mês anterior."
                        )
                        continue
                key = (
                    kind, row["year"], row["month"], row["description"],
                    category, row["value"], row["boe"], row.get("notes"),
                )

            duplicate = key in seen or self._exists(row)
            seen.add(key)
            row["duplicate"] = duplicate
            if duplicate:
                duplicates += 1
                warnings.append(
                    f"Linha {row['line']}: lançamento duplicado será ignorado."
                )

        if source.detected_type == "FLUXO_CAIXA" and not rows:
            errors.append("Nenhum lançamento Financeiro foi encontrado no arquivo.")
        if rows and not errors and not any(
            not row.get("skip") and not row.get("duplicate") for row in rows
        ):
            errors.append(
                "Nenhum lançamento novo pode ser importado; o arquivo contém apenas "
                "Receita Direta originada de BOE ou registros duplicados."
            )

        return FinancialImportValidation(
            file_name=Path(file_name or source.file_path.name).name,
            detected_type=source.detected_type,
            preview=tuple(rows),
            warnings=tuple(dict.fromkeys(warnings)),
            errors=tuple(dict.fromkeys(errors)),
            duplicates=duplicates,
            total=source.total,
        )

    def _is_january_2026_historical_direct(self, row: dict) -> bool:
        if (row["year"], row["month"]) != (2026, 1):
            return False
        previous_boe = self.session.scalar(select(BOEImport.id).where(
            BOEImport.periodo_ano == 2025,
            BOEImport.periodo_mes == 12,
            BOEImport.status == "imported",
        ))
        return previous_boe is None

    def stage_import(
        self, file_path: str | Path, *, file_name: str | None = None
    ) -> tuple[FinancialImportValidation, tuple[object, ...]]:
        validation = self.validate(file_path, file_name=file_name)
        if not validation.can_import:
            raise FinancialImportValidationError(validation)

        entries: list[object] = []
        try:
            for row in validation.preview:
                if row.get("skip") or row.get("duplicate"):
                    continue
                entry = self._entry(row)
                self.session.add(entry)
                entries.append(entry)
            self.session.flush()
        except Exception:
            self.session.rollback()
            raise
        return validation, tuple(entries)

    def _exists(self, row: dict) -> bool:
        if row.get("balance_type"):
            statement = select(FinancialBalanceEntry.id).where(
                FinancialBalanceEntry.year == row["year"],
                FinancialBalanceEntry.month == row["month"],
                FinancialBalanceEntry.balance_type == row["balance_type"],
            )
        elif row["type"] in {"APLICACAO", "RESGATE"}:
            statement = select(InvestmentMovement.id).where(
                InvestmentMovement.periodo_ano == row["year"],
                InvestmentMovement.periodo_mes == row["month"],
                InvestmentMovement.tipo == row["type"],
                InvestmentMovement.descricao == row["description"],
                InvestmentMovement.valor == row["value"],
                InvestmentMovement.observacao == row.get("notes"),
            )
        else:
            statement = select(CashflowEntry.id).where(
                CashflowEntry.periodo_ano == row["year"],
                CashflowEntry.periodo_mes == row["month"],
                CashflowEntry.tipo == row["type"],
                CashflowEntry.descricao == row["description"],
                CashflowEntry.categoria == row["category"],
                CashflowEntry.valor == row["value"],
                CashflowEntry.boe == row["boe"],
                CashflowEntry.observacao == row.get("notes"),
            )
        return self.session.scalar(statement) is not None

    @staticmethod
    def _entry(row: dict) -> object:
        notes = row.get("notes")
        if row.get("balance_type"):
            return FinancialBalanceEntry(
                year=row["year"], month=row["month"],
                balance_type=row["balance_type"], value=row["value"],
                description=row["description"], notes=notes,
            )
        if row["type"] in {"APLICACAO", "RESGATE"}:
            return InvestmentMovement(
                data_movimento=date(row["year"], row["month"], 1),
                periodo_ano=row["year"], periodo_mes=row["month"],
                tipo=row["type"], descricao=row["description"],
                valor=row["value"], observacao=notes,
            )
        return CashflowEntry(
            periodo_ano=row["year"], periodo_mes=row["month"],
            data_lancamento=date(row["year"], row["month"], 1),
            descricao=row["description"], tipo=row["type"], origem="MANUAL",
            categoria=row["category"], valor=row["value"], boe=row["boe"],
            observacao=notes,
        )
