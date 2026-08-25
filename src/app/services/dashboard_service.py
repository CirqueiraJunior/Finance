from dataclasses import dataclass
from decimal import Decimal

from app.models.target_entry import TargetIndicator
from app.services.boe_service import BOEService
from app.services.budget_service import BudgetService
from app.services.financial_flow_service import FinancialFlowService
from app.services.target_service import TargetService


@dataclass(frozen=True, slots=True)
class FinancialDashboardSummary:
    total_revenue: Decimal
    total_expense: Decimal
    operational_result: Decimal
    applications: Decimal
    redemptions: Decimal
    cash_movement: Decimal
    applied_balance: Decimal


@dataclass(frozen=True, slots=True)
class BOEDashboardSummary:
    has_data: bool
    entities: int
    queries: int
    total_value: Decimal


@dataclass(frozen=True, slots=True)
class BudgetDashboardSummary:
    budgeted_revenue: Decimal
    actual_revenue: Decimal
    budgeted_expense: Decimal
    actual_expense: Decimal
    budgeted_result: Decimal
    actual_result: Decimal


@dataclass(frozen=True, slots=True)
class IndicatorDashboardSummary:
    has_data: bool
    target: Decimal
    actual: Decimal
    achievement_percentage: Decimal | None


@dataclass(frozen=True, slots=True)
class TargetDashboardSummary:
    queries: IndicatorDashboardSummary
    registrations: IndicatorDashboardSummary


@dataclass(frozen=True, slots=True)
class DashboardSummary:
    year: int
    month: int
    financial: FinancialDashboardSummary
    boe: BOEDashboardSummary
    budget: BudgetDashboardSummary
    targets: TargetDashboardSummary


class DashboardService:
    """Read-only orchestration of previously homologated domain services."""

    def __init__(
        self,
        financial_flow: FinancialFlowService,
        boe: BOEService,
        budget: BudgetService,
        targets: TargetService,
    ) -> None:
        sessions = {
            id(financial_flow.cashflow.repository.session),
            id(financial_flow.investments.repository.session),
            id(boe.repository.session),
            id(budget.repository.session),
            id(targets.repository.session),
        }
        if len(sessions) != 1:
            raise ValueError("Os serviços do Dashboard devem compartilhar a sessão.")
        self.financial_flow = financial_flow
        self.boe = boe
        self.budget = budget
        self.targets = targets

    def get_dashboard_summary(self, year: int, month: int) -> DashboardSummary:
        financial = self.financial_flow.get_summary(year, month)
        boe_details = self.boe.get_period_details(year, month)
        budget = self.budget.get_budget_vs_actual(year, month).summary
        queries = self.targets.get_target_vs_actual(
            year, month, TargetIndicator.QUERIES
        )
        registrations = self.targets.get_target_vs_actual(
            year, month, TargetIndicator.REGISTRATIONS
        )

        zero = Decimal("0.0000")
        return DashboardSummary(
            year=year,
            month=month,
            financial=FinancialDashboardSummary(
                financial.total_revenue,
                financial.total_expense,
                financial.operational_result,
                financial.applications,
                financial.redemptions,
                financial.cash_movement,
                financial.applied_balance,
            ),
            boe=(
                BOEDashboardSummary(False, 0, 0, zero)
                if boe_details is None
                else BOEDashboardSummary(
                    True,
                    boe_details.total_entities,
                    boe_details.total_queries,
                    boe_details.total_value,
                )
            ),
            budget=BudgetDashboardSummary(
                budget.budgeted_revenue,
                budget.actual_revenue,
                budget.budgeted_expense,
                budget.actual_expense,
                budget.budgeted_result,
                budget.actual_result,
            ),
            targets=TargetDashboardSummary(
                self._indicator(queries),
                self._indicator(registrations),
            ),
        )

    @staticmethod
    def _indicator(result) -> IndicatorDashboardSummary:
        summary = result.summary
        return IndicatorDashboardSummary(
            bool(result.comparisons),
            summary.target_total,
            summary.actual_total,
            summary.achievement_percentage,
        )
