from datetime import date
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import CashflowDuplicateBOEError, CashflowValidationError
from app.models.boe_import import BOEImport
from app.models.cashflow_entry import (
    EXPENSE_CATEGORIES,
    CashflowCategory,
    CashflowEntry,
    CashflowOrigin,
    CashflowType,
)
from app.repositories.cashflow_repository import CashflowRepository


@dataclass(frozen=True, slots=True)
class CashflowSummary:
    direct_revenue: Decimal
    indirect_revenue: Decimal
    total_revenue: Decimal
    total_expense: Decimal
    monthly_balance: Decimal


class CashflowService:
    def __init__(self, repository: CashflowRepository) -> None:
        self.repository = repository

    def create_direct_revenue_from_boe(
        self, boe_import: BOEImport, *, commit: bool = True
    ) -> CashflowEntry:
        if boe_import.id is None:
            raise CashflowValidationError("A importação BOE deve estar persistida.")
        if boe_import.status != "imported":
            raise CashflowValidationError(
                "Somente BOE com status imported pode gerar Receita Direta."
            )
        if self.repository.exists_for_boe_import(boe_import.id):
            raise CashflowDuplicateBOEError(
                "Esta importação BOE já possui uma Receita Direta."
            )
        entry = CashflowEntry(
            periodo_ano=boe_import.periodo_ano,
            periodo_mes=boe_import.periodo_mes,
            data_lancamento=date(boe_import.periodo_ano, boe_import.periodo_mes, 1),
            descricao=(
                f"Receita Direta BOE {boe_import.periodo_mes:02d}/"
                f"{boe_import.periodo_ano}"
            ),
            tipo=CashflowType.REVENUE.value,
            origem=CashflowOrigin.BOE.value,
            categoria=CashflowCategory.DIRECT_REVENUE.value,
            valor=self._positive_decimal(boe_import.valor_total),
            boe_import_id=boe_import.id,
            observacao=f"Gerada automaticamente a partir de {boe_import.nome_arquivo}.",
        )
        return self._persist(entry, commit=commit)

    def create_indirect_revenue(
        self,
        *,
        year: int,
        month: int,
        entry_date: date,
        description: str,
        value: Decimal | str,
        notes: str | None = None,
    ) -> CashflowEntry:
        if not isinstance(entry_date, date):
            raise CashflowValidationError("A data do lançamento é inválida.")
        normalized_notes = notes.strip() if notes and notes.strip() else None
        entry = CashflowEntry(
            periodo_ano=self._valid_year(year),
            periodo_mes=self._valid_month(month),
            data_lancamento=entry_date,
            descricao=self._required_text(description, "descrição"),
            tipo=CashflowType.REVENUE.value,
            origem=CashflowOrigin.MANUAL.value,
            categoria=CashflowCategory.INDIRECT_REVENUE.value,
            valor=self._positive_decimal(value),
            boe_import_id=None,
            observacao=normalized_notes,
        )
        return self._persist(entry, commit=True)

    def create_expense(
        self,
        *,
        year: int,
        month: int,
        entry_date: date,
        description: str,
        category: CashflowCategory | str,
        value: Decimal | str,
        notes: str | None = None,
    ) -> CashflowEntry:
        if not isinstance(entry_date, date):
            raise CashflowValidationError("A data do lançamento é inválida.")
        normalized_category = self._expense_category(category)
        normalized_notes = notes.strip() if notes and notes.strip() else None
        entry = CashflowEntry(
            periodo_ano=self._valid_year(year),
            periodo_mes=self._valid_month(month),
            data_lancamento=entry_date,
            descricao=self._required_text(description, "descrição"),
            tipo=CashflowType.EXPENSE.value,
            origem=CashflowOrigin.MANUAL.value,
            categoria=normalized_category.value,
            valor=self._positive_decimal(value),
            boe_import_id=None,
            observacao=normalized_notes,
        )
        return self._persist(entry, commit=True)

    def get_entry(self, entry_id: int) -> CashflowEntry | None:
        return self.repository.get_by_id(entry_id)

    def list_entries(self) -> list[CashflowEntry]:
        return self.repository.list_all()

    def list_entries_by_period(self, year: int, month: int) -> list[CashflowEntry]:
        return self.repository.list_by_period(
            self._valid_year(year), self._valid_month(month)
        )

    def get_monthly_summary(self, year: int, month: int) -> CashflowSummary:
        entries = self.list_entries_by_period(year, month)
        zero = Decimal("0.0000")
        direct = sum(
            (entry.valor for entry in entries if entry.categoria == CashflowCategory.DIRECT_REVENUE.value),
            zero,
        )
        indirect = sum(
            (entry.valor for entry in entries if entry.categoria == CashflowCategory.INDIRECT_REVENUE.value),
            zero,
        )
        expenses = sum(
            (entry.valor for entry in entries if entry.tipo == CashflowType.EXPENSE.value),
            zero,
        )
        total_revenue = direct + indirect
        return CashflowSummary(
            direct_revenue=direct,
            indirect_revenue=indirect,
            total_revenue=total_revenue,
            total_expense=expenses,
            monthly_balance=total_revenue - expenses,
        )

    def _persist(self, entry: CashflowEntry, *, commit: bool) -> CashflowEntry:
        try:
            self.repository.add(entry)
            if commit:
                self.repository.session.commit()
                self.repository.session.refresh(entry)
            return entry
        except IntegrityError as error:
            self.repository.session.rollback()
            if entry.boe_import_id is not None:
                raise CashflowDuplicateBOEError(
                    "Esta importação BOE já possui uma Receita Direta."
                ) from error
            raise CashflowValidationError(
                "O lançamento financeiro não atende às regras de consistência."
            ) from error

    @staticmethod
    def _valid_year(value: int) -> int:
        try:
            year = int(value)
        except (TypeError, ValueError) as error:
            raise CashflowValidationError("O ano é inválido.") from error
        if not 2000 <= year <= 9999:
            raise CashflowValidationError("O ano é inválido.")
        return year

    @staticmethod
    def _valid_month(value: int) -> int:
        try:
            month = int(value)
        except (TypeError, ValueError) as error:
            raise CashflowValidationError("O mês é inválido.") from error
        if not 1 <= month <= 12:
            raise CashflowValidationError("O mês é inválido.")
        return month

    @staticmethod
    def _positive_decimal(value: Decimal | str) -> Decimal:
        if isinstance(value, float):
            raise CashflowValidationError("O valor não pode usar ponto flutuante.")
        try:
            amount = Decimal(value).quantize(Decimal("0.0001"))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise CashflowValidationError("O valor é inválido.") from error
        if not amount.is_finite() or amount <= 0:
            raise CashflowValidationError("O valor deve ser maior que zero.")
        return amount

    @staticmethod
    def _required_text(value: str, field_name: str) -> str:
        normalized = value.strip() if isinstance(value, str) else ""
        if not normalized:
            raise CashflowValidationError(f"O campo {field_name} é obrigatório.")
        return normalized

    @staticmethod
    def _expense_category(value: CashflowCategory | str) -> CashflowCategory:
        try:
            category = CashflowCategory(value)
        except ValueError as error:
            raise CashflowValidationError("A categoria de despesa é inválida.") from error
        if category not in EXPENSE_CATEGORIES:
            raise CashflowValidationError("A categoria de despesa é inválida.")
        return category
