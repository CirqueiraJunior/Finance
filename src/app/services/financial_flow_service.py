from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.models.investment_movement import InvestmentMovementType
from app.services.cashflow_service import CashflowService
from app.services.investment_service import InvestmentService


@dataclass(frozen=True, slots=True)
class FinancialMovement:
    movement_date: date
    movement_type: str
    description: str
    category: str | None
    origin: str | None
    value: Decimal
    boe: bool = False


@dataclass(frozen=True, slots=True)
class FinancialFlowSummary:
    direct_revenue: Decimal
    indirect_revenue: Decimal
    total_revenue: Decimal
    total_expense: Decimal
    applications: Decimal
    redemptions: Decimal
    operational_result: Decimal
    cash_movement: Decimal
    applied_balance: Decimal


class FinancialFlowService:
    """Combines operational and investment movements for the Financeiro use case."""

    def __init__(
        self, cashflow: CashflowService, investments: InvestmentService
    ) -> None:
        if cashflow.repository.session is not investments.repository.session:
            raise ValueError("Os serviços financeiros devem compartilhar a sessão.")
        self.cashflow = cashflow
        self.investments = investments

    def list_by_period(self, year: int, month: int) -> list[FinancialMovement]:
        movements = [
            FinancialMovement(
                item.data_lancamento, item.tipo, item.descricao,
                item.categoria, item.origem, item.valor, item.boe,
            )
            for item in self.cashflow.list_entries_by_period(year, month)
        ]
        movements.extend(
            FinancialMovement(
                item.data_movimento, item.tipo, item.descricao,
                (
                    "INVESTIMENTO"
                    if item.tipo == InvestmentMovementType.APPLICATION.value
                    else "RESGATE"
                ),
                "MANUAL", item.valor, False,
            )
            for item in self.investments.list_by_period(year, month)
        )
        return sorted(
            movements,
            key=lambda item: (item.movement_date, item.movement_type, item.description),
        )

    def get_summary(self, year: int, month: int) -> FinancialFlowSummary:
        operational = self.cashflow.get_monthly_summary(year, month)
        investments = self.investments.get_monthly_summary(year, month)
        cash_movement = (
            operational.total_revenue
            - operational.total_expense
            - investments.applications
            + investments.redemptions
        )
        return FinancialFlowSummary(
            operational.direct_revenue,
            operational.indirect_revenue,
            operational.total_revenue,
            operational.total_expense,
            investments.applications,
            investments.redemptions,
            operational.monthly_balance,
            cash_movement,
            investments.applied_balance,
        )

    def create_application(self, **values):
        return self.investments.create_application(**values)

    def create_redemption(self, **values):
        return self.investments.create_redemption(**values)

    @staticmethod
    def is_investment_type(value: str) -> bool:
        return value in {
            InvestmentMovementType.APPLICATION.value,
            InvestmentMovementType.REDEMPTION.value,
        }
