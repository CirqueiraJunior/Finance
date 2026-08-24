from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import InvestmentBalanceError, InvestmentValidationError
from app.models.investment_movement import InvestmentMovement, InvestmentMovementType
from app.repositories.investment_repository import InvestmentRepository


@dataclass(frozen=True, slots=True)
class InvestmentMonthlySummary:
    applications: Decimal
    redemptions: Decimal
    net_movement: Decimal
    applied_balance: Decimal


class InvestmentService:
    def __init__(self, repository: InvestmentRepository) -> None:
        self.repository = repository

    def create_application(
        self, *, movement_date: date, description: str,
        value: Decimal | str, notes: str | None = None,
    ) -> InvestmentMovement:
        return self._create(
            movement_date, InvestmentMovementType.APPLICATION, description, value, notes
        )

    def create_redemption(
        self, *, movement_date: date, description: str,
        value: Decimal | str, notes: str | None = None,
    ) -> InvestmentMovement:
        normalized_date = self._valid_date(movement_date)
        amount = self._positive_decimal(value)
        available = self.get_applied_balance(normalized_date)
        minimum_future_balance = self._minimum_balance_from(normalized_date)
        if amount > available or amount > minimum_future_balance:
            raise InvestmentBalanceError(
                f"Saldo disponível: {self._currency(available)}. "
                f"Resgate solicitado: {self._currency(amount)}."
            )
        return self._create(
            normalized_date, InvestmentMovementType.REDEMPTION,
            description, amount, notes,
        )

    def _minimum_balance_from(self, movement_date: date) -> Decimal:
        balance = Decimal("0.0000")
        balances = []
        for movement in self.repository.list_all():
            if movement.tipo == InvestmentMovementType.APPLICATION.value:
                balance += movement.valor
            else:
                balance -= movement.valor
            if movement.data_movimento >= movement_date:
                balances.append(balance)
        return min(balances, default=self.get_applied_balance(movement_date))

    def get_movement(self, movement_id: int) -> InvestmentMovement | None:
        return self.repository.get_by_id(movement_id)

    def list_movements(self) -> list[InvestmentMovement]:
        return self.repository.list_all()

    def list_by_period(self, year: int, month: int) -> list[InvestmentMovement]:
        return self.repository.list_by_period(
            self._valid_year(year), self._valid_month(month)
        )

    def get_applied_balance(self, end_date: date | None = None) -> Decimal:
        movements = (
            self.repository.list_all()
            if end_date is None
            else self.repository.list_until_date(self._valid_date(end_date))
        )
        zero = Decimal("0.0000")
        applications = sum(
            (item.valor for item in movements
             if item.tipo == InvestmentMovementType.APPLICATION.value), zero
        )
        redemptions = sum(
            (item.valor for item in movements
             if item.tipo == InvestmentMovementType.REDEMPTION.value), zero
        )
        return applications - redemptions

    def get_monthly_summary(self, year: int, month: int) -> InvestmentMonthlySummary:
        normalized_year = self._valid_year(year)
        normalized_month = self._valid_month(month)
        movements = self.repository.list_by_period(normalized_year, normalized_month)
        zero = Decimal("0.0000")
        applications = sum(
            (item.valor for item in movements
             if item.tipo == InvestmentMovementType.APPLICATION.value), zero
        )
        redemptions = sum(
            (item.valor for item in movements
             if item.tipo == InvestmentMovementType.REDEMPTION.value), zero
        )
        end_date = date(
            normalized_year, normalized_month,
            monthrange(normalized_year, normalized_month)[1],
        )
        return InvestmentMonthlySummary(
            applications, redemptions, applications - redemptions,
            self.get_applied_balance(end_date),
        )

    def _create(
        self, movement_date: date, movement_type: InvestmentMovementType,
        description: str, value: Decimal | str, notes: str | None,
    ) -> InvestmentMovement:
        normalized_date = self._valid_date(movement_date)
        movement = InvestmentMovement(
            data_movimento=normalized_date,
            periodo_ano=normalized_date.year,
            periodo_mes=normalized_date.month,
            tipo=movement_type.value,
            descricao=self._required_text(description),
            valor=self._positive_decimal(value),
            observacao=self._optional_text(notes),
        )
        try:
            self.repository.add(movement)
            self.repository.session.commit()
            self.repository.session.refresh(movement)
            return movement
        except IntegrityError as error:
            self.repository.session.rollback()
            raise InvestmentValidationError(
                "Não foi possível cadastrar a movimentação."
            ) from error

    @staticmethod
    def _valid_date(value: date) -> date:
        if not isinstance(value, date):
            raise InvestmentValidationError("A data do movimento é inválida.")
        if not 2000 <= value.year <= 9999:
            raise InvestmentValidationError("O ano do movimento é inválido.")
        return value

    @staticmethod
    def _valid_year(value: int) -> int:
        if not isinstance(value, int) or not 2000 <= value <= 9999:
            raise InvestmentValidationError("O ano é inválido.")
        return value

    @staticmethod
    def _valid_month(value: int) -> int:
        if not isinstance(value, int) or not 1 <= value <= 12:
            raise InvestmentValidationError("O mês é inválido.")
        return value

    @staticmethod
    def _positive_decimal(value: Decimal | str) -> Decimal:
        if isinstance(value, float):
            raise InvestmentValidationError("O valor não pode usar float.")
        try:
            amount = Decimal(value).quantize(Decimal("0.0001"))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise InvestmentValidationError("O valor é inválido.") from error
        if not amount.is_finite() or amount <= 0:
            raise InvestmentValidationError("O valor deve ser maior que zero.")
        return amount

    @staticmethod
    def _required_text(value: str) -> str:
        normalized = value.strip() if isinstance(value, str) else ""
        if not normalized:
            raise InvestmentValidationError("A descrição é obrigatória.")
        return normalized

    @staticmethod
    def _optional_text(value: str | None) -> str | None:
        normalized = value.strip() if isinstance(value, str) else ""
        return normalized or None

    @staticmethod
    def _currency(value: Decimal) -> str:
        formatted = f"{value:,.4f}".replace(",", "_").replace(".", ",").replace("_", ".")
        return f"R$ {formatted}"
