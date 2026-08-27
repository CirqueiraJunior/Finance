from dataclasses import dataclass
from decimal import Decimal

from app.services.boe_service import BOEService
from app.services.budget_service import BudgetService
from app.services.financial_flow_service import FinancialFlowService


@dataclass(frozen=True, slots=True)
class MonthlyReportRow:
    month: int
    total_revenue: Decimal
    total_expense: Decimal
    operational_result: Decimal
    applications: Decimal
    redemptions: Decimal
    cash_movement: Decimal
    applied_balance: Decimal
    boe_value: Decimal
    budgeted_result: Decimal


@dataclass(frozen=True, slots=True)
class AnnualReport:
    year: int
    rows: tuple[MonthlyReportRow, ...]


class ReportService:
    """Read-only annual executive report built from approved domain services."""

    def __init__(
        self,
        financial_flow: FinancialFlowService,
        boe: BOEService,
        budget: BudgetService,
    ) -> None:
        self.financial_flow = financial_flow
        self.boe = boe
        self.budget = budget

    def get_annual_report(self, year: int) -> AnnualReport:
        year = self._year(year)
        rows: list[MonthlyReportRow] = []
        for month in range(1, 13):
            financial = self.financial_flow.get_summary(year, month)
            budget = self.budget.get_budget_vs_actual(year, month).summary
            boe_value = self._boe_value(year, month)
            rows.append(
                MonthlyReportRow(
                    month=month,
                    total_revenue=financial.total_revenue,
                    total_expense=financial.total_expense,
                    operational_result=financial.operational_result,
                    applications=financial.applications,
                    redemptions=financial.redemptions,
                    cash_movement=financial.cash_movement,
                    applied_balance=financial.applied_balance,
                    boe_value=boe_value,
                    budgeted_result=budget.budgeted_result,
                )
            )
        return AnnualReport(year, tuple(rows))

    def _boe_value(self, year: int, month: int) -> Decimal:
        for item in self.boe.list_imports():
            if (
                item.periodo_ano == year
                and item.periodo_mes == month
                and item.status == "imported"
            ):
                return item.valor_total
        return Decimal("0.0000")

    @staticmethod
    def _year(value: int) -> int:
        try:
            year = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError("Ano inválido.") from error
        if not 2000 <= year <= 9999:
            raise ValueError("Ano inválido.")
        return year
