from dataclasses import dataclass
from decimal import Decimal

from app.repositories.financial_balance_repository import FinancialBalanceRepository
from app.services.financial_flow_service import FinancialFlowService


@dataclass(frozen=True, slots=True)
class FinancialPosition:
    year: int
    month: int
    opening_balance: Decimal
    bank_balance: Decimal
    net_revenue: Decimal
    monthly_movement: Decimal
    applied_balance: Decimal | None


class FinancialBalanceService:
    def __init__(self, repository: FinancialBalanceRepository,
                 financial_flow: FinancialFlowService) -> None:
        self.repository = repository
        self.financial_flow = financial_flow

    def position(self, year: int, month: int) -> FinancialPosition | None:
        base = self.repository.base(year, month)
        if base is None or (year, month) < (base.year, base.month):
            return None
        opening = base.value
        selected_movement = Decimal("0")
        for current_year, current_month in self._periods(base.year, base.month, year, month):
            calculated = self._movement(current_year, current_month)
            if calculated is None:
                return None
            movement, net_revenue = calculated
            if (current_year, current_month) == (year, month):
                selected_movement = movement
                selected_net = net_revenue
                break
            opening += movement
        applied = self.repository.get(year, month, "SALDO_APLICADO")
        return FinancialPosition(year, month, opening, opening + selected_movement,
                                 selected_net, selected_movement,
                                 applied.value if applied else None)

    def _movement(self, year: int, month: int) -> tuple[Decimal, Decimal] | None:
        cash = self.financial_flow.cashflow.get_monthly_summary(year, month)
        if not cash.direct_revenue_available:
            return None
        investments = self.financial_flow.investments.get_monthly_summary(year, month)
        net_revenue = cash.total_revenue - cash.boe_expense
        movement = (investments.redemptions + net_revenue
                    - cash.non_boe_expense - investments.applications)
        return movement, net_revenue

    @staticmethod
    def _periods(start_year: int, start_month: int, end_year: int, end_month: int):
        year, month = start_year, start_month
        while (year, month) <= (end_year, end_month):
            yield year, month
            month += 1
            if month == 13:
                year, month = year + 1, 1
