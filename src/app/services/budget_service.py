from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import (
    BudgetDuplicateError,
    BudgetValidationError,
)
from app.models.budget_entry import BudgetEntry
from app.models.cashflow_entry import (
    EXPENSE_CATEGORIES,
    CashflowCategory,
    CashflowType,
)
from app.repositories.budget_repository import BudgetRepository
from app.repositories.cashflow_repository import CashflowRepository


REVENUE_CATEGORIES = (
    CashflowCategory.DIRECT_REVENUE,
    CashflowCategory.INDIRECT_REVENUE,
)


@dataclass(frozen=True, slots=True)
class BudgetComparison:
    entry_type: str
    description: str | None
    category: str
    budgeted: Decimal
    actual: Decimal
    absolute_variance: Decimal
    percentage_variance: Decimal | None


@dataclass(frozen=True, slots=True)
class BudgetSummary:
    budgeted_revenue: Decimal
    actual_revenue: Decimal
    budgeted_expense: Decimal
    actual_expense: Decimal
    budgeted_result: Decimal
    actual_result: Decimal


@dataclass(frozen=True, slots=True)
class BudgetVsActual:
    comparisons: tuple[BudgetComparison, ...]
    summary: BudgetSummary


class BudgetService:
    def __init__(
        self,
        repository: BudgetRepository,
        cashflow_repository: CashflowRepository,
    ) -> None:
        if repository.session is not cashflow_repository.session:
            raise ValueError("Orçamento e Fluxo de Caixa devem compartilhar a sessão.")
        self.repository = repository
        self.cashflow_repository = cashflow_repository

    def create_budget(
        self,
        *,
        year: int,
        month: int,
        entry_type: CashflowType | str,
        category: CashflowCategory | str,
        budgeted_value: Decimal | str,
        descricao: str | None = None,
        notes: str | None = None,
    ) -> BudgetEntry:
        normalized_year = self._valid_year(year)
        normalized_month = self._valid_month(month)
        normalized_type, normalized_category = self._valid_combination(
            entry_type, category
        )
        if self.repository.exists(
            normalized_year,
            normalized_month,
            normalized_type.value,
            normalized_category.value,
        ):
            raise BudgetDuplicateError(
                "Já existe orçamento para este período, tipo e categoria."
            )
        budget = BudgetEntry(
            periodo_ano=normalized_year,
            periodo_mes=normalized_month,
            tipo=normalized_type.value,
            categoria=normalized_category.value,
            descricao=self._description(descricao),
            valor_orcado=self._non_negative_decimal(budgeted_value),
            observacao=self._optional_text(notes),
        )
        return self._persist(budget)

    def update_budget(
        self,
        budget_id: int,
        *,
        budgeted_value: Decimal | str,
        descricao: str | None = None,
        notes: str | None = None,
    ) -> BudgetEntry:
        budget = self.repository.get_by_id(budget_id)
        if budget is None:
            raise BudgetValidationError("Orçamento não encontrado.")
        budget.valor_orcado = self._non_negative_decimal(budgeted_value)
        if descricao is not None:
            budget.descricao = self._description(descricao)
        budget.observacao = self._optional_text(notes)
        try:
            self.repository.session.commit()
            self.repository.session.refresh(budget)
        except IntegrityError as error:
            self.repository.session.rollback()
            raise BudgetValidationError("Não foi possível atualizar o orçamento.") from error
        return budget

    def get_budget(self, budget_id: int) -> BudgetEntry | None:
        return self.repository.get_by_id(budget_id)

    def list_by_period(self, year: int, month: int) -> list[BudgetEntry]:
        return self.repository.list_by_period(
            self._valid_year(year), self._valid_month(month)
        )

    def list_by_year(self, year: int) -> list[BudgetEntry]:
        return self.repository.list_by_year(self._valid_year(year))

    def get_budget_vs_actual(
        self, year: int, month: int | None = None
    ) -> BudgetVsActual:
        normalized_year = self._valid_year(year)
        if month is None:
            budgets = self.repository.list_by_year(normalized_year)
            actual_entries = [
                entry for entry in self.cashflow_repository.list_all()
                if entry.periodo_ano == normalized_year
            ]
        else:
            normalized_month = self._valid_month(month)
            budgets = self.repository.list_by_period(normalized_year, normalized_month)
            actual_entries = self.cashflow_repository.list_by_period(
                normalized_year, normalized_month
            )

        zero = Decimal("0.0000")
        budget_values: dict[tuple[str, str], Decimal] = {}
        budget_descriptions: dict[tuple[str, str], set[str]] = {}
        actual_values: dict[tuple[str, str], Decimal] = {}
        for budget in budgets:
            key = (budget.tipo, budget.categoria)
            budget_values[key] = budget_values.get(key, zero) + budget.valor_orcado
            if budget.descricao:
                budget_descriptions.setdefault(key, set()).add(budget.descricao)
        for entry in actual_entries:
            key = (entry.tipo, entry.categoria)
            actual_values[key] = actual_values.get(key, zero) + entry.valor

        comparisons = []
        for entry_type, category in sorted(set(budget_values) | set(actual_values)):
            budgeted = budget_values.get((entry_type, category), zero)
            actual = actual_values.get((entry_type, category), zero)
            variance = (
                actual - budgeted
                if entry_type == CashflowType.REVENUE.value
                else budgeted - actual
            )
            percentage = None
            if budgeted > 0:
                percentage = (variance / budgeted * Decimal("100")).quantize(
                    Decimal("0.0001")
                )
            comparisons.append(
                BudgetComparison(
                    entry_type,
                    " / ".join(sorted(budget_descriptions.get((entry_type, category), set()))) or None,
                    category, budgeted, actual, variance, percentage
                )
            )

        budgeted_revenue = sum(
            (value for (kind, _), value in budget_values.items()
             if kind == CashflowType.REVENUE.value), zero
        )
        actual_revenue = sum(
            (value for (kind, _), value in actual_values.items()
             if kind == CashflowType.REVENUE.value), zero
        )
        budgeted_expense = sum(
            (value for (kind, _), value in budget_values.items()
             if kind == CashflowType.EXPENSE.value), zero
        )
        actual_expense = sum(
            (value for (kind, _), value in actual_values.items()
             if kind == CashflowType.EXPENSE.value), zero
        )
        summary = BudgetSummary(
            budgeted_revenue,
            actual_revenue,
            budgeted_expense,
            actual_expense,
            budgeted_revenue - budgeted_expense,
            actual_revenue - actual_expense,
        )
        return BudgetVsActual(tuple(comparisons), summary)

    def _persist(self, budget: BudgetEntry) -> BudgetEntry:
        try:
            self.repository.add(budget)
            self.repository.session.commit()
            self.repository.session.refresh(budget)
            return budget
        except IntegrityError as error:
            self.repository.session.rollback()
            raise BudgetDuplicateError(
                "Já existe orçamento para este período, tipo e categoria."
            ) from error

    @staticmethod
    def _valid_combination(
        entry_type: CashflowType | str,
        category: CashflowCategory | str,
    ) -> tuple[CashflowType, CashflowCategory]:
        try:
            normalized_type = CashflowType(entry_type)
            normalized_category = CashflowCategory(category)
        except ValueError as error:
            raise BudgetValidationError("Tipo ou categoria inválida.") from error
        allowed = (
            REVENUE_CATEGORIES
            if normalized_type is CashflowType.REVENUE
            else EXPENSE_CATEGORIES
        )
        if normalized_category not in allowed:
            raise BudgetValidationError("A categoria não corresponde ao tipo.")
        return normalized_type, normalized_category

    @staticmethod
    def _valid_year(value: int) -> int:
        try:
            year = int(value)
        except (TypeError, ValueError) as error:
            raise BudgetValidationError("O ano é inválido.") from error
        if not 2000 <= year <= 9999:
            raise BudgetValidationError("O ano é inválido.")
        return year

    @staticmethod
    def _valid_month(value: int) -> int:
        try:
            month = int(value)
        except (TypeError, ValueError) as error:
            raise BudgetValidationError("O mês é inválido.") from error
        if not 1 <= month <= 12:
            raise BudgetValidationError("O mês é inválido.")
        return month

    @staticmethod
    def _non_negative_decimal(value: Decimal | str) -> Decimal:
        if isinstance(value, float):
            raise BudgetValidationError("O valor orçado não pode usar float.")
        try:
            amount = Decimal(value).quantize(Decimal("0.0001"))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise BudgetValidationError("O valor orçado é inválido.") from error
        if not amount.is_finite() or amount < 0:
            raise BudgetValidationError("O valor orçado não pode ser negativo.")
        return amount

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        normalized = value.strip() if isinstance(value, str) else ""
        return normalized or None

    @staticmethod
    def _description(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise BudgetValidationError("A descrição é obrigatória.")
        if len(normalized) > 255:
            raise BudgetValidationError("A descrição deve possuir no máximo 255 caracteres.")
        return normalized
