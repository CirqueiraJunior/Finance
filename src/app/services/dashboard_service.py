from dataclasses import dataclass
from decimal import Decimal

from app.models.target_entry import TargetIndicator
from app.services.boe_service import BOEService
from app.services.budget_service import BudgetService
from app.services.financial_flow_service import FinancialFlowService
from app.services.target_service import TargetService
from app.services.ranking_service import RankingService
from app.repositories.financial_balance_repository import FinancialBalanceRepository
from app.repositories.dashboard_repository import DashboardRepository, ZERO
from app.services.financial_balance_service import FinancialBalanceService


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
        ranking: RankingService | None = None,
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
        self.ranking = ranking
        self.analytics = DashboardRepository(financial_flow.cashflow.repository.session)

    def get_dashboard_data(self, year: int, month: int, **filters) -> dict:
        return {
            "financial": self.get_financial_dashboard(
                year, month, filters.get("category"), filters.get("entry_type")
            ),
            "boe": self.get_boe_dashboard(
                year, month, filters.get("boe_entity_id"),
                filters.get("boe_start_month"), filters.get("boe_end_month"),
            ),
            "targets": self.get_targets_dashboard(
                year, month, filters.get("target_entity_id"),
                filters.get("indicator", "TODAS"),
                filters.get("target_start_month"), filters.get("target_end_month"),
            ),
        }

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

    def get_financial_dashboard(self, year: int, month: int,
                                category: str | None = None,
                                entry_type: str | None = None) -> dict:
        category = category or None
        entry_type = entry_type or None
        aggregates = self.analytics.financial_year(year, category, entry_type)
        official = (aggregates if not category and not entry_type
                    else self.analytics.financial_year(year))
        balance_service = FinancialBalanceService(
            FinancialBalanceRepository(self.financial_flow.cashflow.repository.session),
            self.financial_flow,
        )
        january = balance_service.position(year, 1)
        running_opening = january.opening_balance if january else None
        monthly = []
        for selected_month in range(1, 13):
            cash = aggregates["cash"].get(selected_month)
            investment = aggregates["investments"].get(selected_month)
            direct = aggregates["direct"].get(selected_month, ZERO)
            indirect = cash.indirect if cash else ZERO
            expense = cash.expense if cash else ZERO
            applications = investment.applications if investment else ZERO
            redemptions = investment.redemptions if investment else ZERO
            budget = aggregates["budget"][selected_month]

            official_cash = official["cash"].get(selected_month)
            official_investment = official["investments"].get(selected_month)
            official_direct = official["direct"].get(selected_month)
            if running_opening is None or official_direct is None:
                opening = bank = None
            else:
                official_indirect = official_cash.indirect if official_cash else ZERO
                official_expense = official_cash.expense if official_cash else ZERO
                official_boe_expense = official_cash.boe_expense if official_cash else ZERO
                official_applications = (official_investment.applications
                                         if official_investment else ZERO)
                official_redemptions = (official_investment.redemptions
                                        if official_investment else ZERO)
                movement = (official_indirect + official_redemptions +
                            official_direct - official_boe_expense -
                            (official_expense - official_boe_expense) -
                            official_applications)
                opening, bank = running_opening, running_opening + movement
                running_opening = bank
            monthly.append({
                "month": selected_month,
                "revenue": direct + indirect, "expense": expense,
                "opening_balance": opening, "bank_balance": bank,
                "applications": applications, "redemptions": redemptions,
                "budgeted_revenue": budget["RECEITA"],
                "actual_revenue": direct + indirect,
                "budgeted_expense": budget["DESPESA"],
                "actual_expense": expense,
            })
        selected = monthly[month - 1]
        selected_cash = aggregates["cash"].get(month)
        selected_direct = aggregates["direct"].get(month, ZERO)
        selected_indirect = selected_cash.indirect if selected_cash else ZERO
        selected_expense = selected_cash.expense if selected_cash else ZERO
        selected_boe_expense = selected_cash.boe_expense if selected_cash else ZERO
        selected_budget = aggregates["budget"][month]
        actual_result = selected["actual_revenue"] - selected["actual_expense"]
        budgeted_result = (selected_budget["RECEITA"] - selected_budget["DESPESA"])
        variance = actual_result - budgeted_result
        variance_percentage = (
            None if budgeted_result == 0
            else variance / abs(budgeted_result) * Decimal("100")
        )
        return {
            "year": year, "month": month,
            "filters": {"category": category, "type": entry_type},
            "balance_available": selected["bank_balance"] is not None,
            "kpis": {
                "opening_balance": selected["opening_balance"],
                "direct_revenue": selected_direct,
                "indirect_revenue": selected_indirect,
                "total_revenue": selected_direct + selected_indirect,
                "net_revenue": selected_direct - selected_boe_expense,
                "total_expense": selected_expense,
                "applications": selected["applications"],
                "redemptions": selected["redemptions"],
                "bank_balance": selected["bank_balance"],
                "applied_balance": aggregates["applied"].get(month),
            },
            "budget": {
                "budgeted_revenue": selected_budget["RECEITA"],
                "actual_revenue": selected["actual_revenue"],
                "budgeted_expense": selected_budget["DESPESA"],
                "actual_expense": selected["actual_expense"],
                "result": actual_result,
                "variance": variance,
                "variance_percentage": variance_percentage,
            },
            "monthly": monthly,
            "revenue_distribution": dict(aggregates["distributions"]["revenue"]),
            "expense_distribution": dict(aggregates["distributions"]["expense"]),
        }

    def get_boe_dashboard(
        self, year: int, month: int, entity_id: int | None = None,
        start_month: int | None = None, end_month: int | None = None,
    ) -> dict:
        aggregates = self.analytics.boe_year(year, entity_id)
        rows = [row for row in aggregates["rows"] if row.periodo_mes == month]
        queries = sum((row.queries for row in rows), 0)
        total = sum((row.value for row in rows), ZERO)
        monthly = []
        for selected_month in self._dashboard_months(start_month, end_month):
            selected_rows = [row for row in aggregates["rows"]
                             if row.periodo_mes == selected_month]
            monthly.append({"month": selected_month,
                            "queries": sum((row.queries for row in selected_rows), 0),
                            "total_value": sum((row.value for row in selected_rows), ZERO)})
        return {
            "year": year, "month": month,
            "unit_value": None if queries == 0 else total / queries,
            "queries": queries, "total_value": total,
            "entity_count": len(rows),
            "filters": {"entities": [{"id": item[0], "code": item[1], "name": item[2]}
                                      for item in aggregates["entities"]]},
            "monthly": monthly,
            "entities": [{
                "id": row.id, "code": row.codigo_entidade, "name": row.nome,
                "queries": row.queries,
                "unit_value": None if row.queries == 0 else row.value / row.queries,
                "total_value": row.value,
            } for row in rows],
        }

    def get_targets_dashboard(
        self, year: int, month: int, entity_id: int | None = None,
        indicator: str = "TODAS",
        start_month: int | None = None, end_month: int | None = None,
    ) -> dict:
        selected = indicator.upper()
        if selected not in {"CONSULTAS", "REGISTROS", "TODAS"}:
            raise ValueError("Indicador inválido.")
        aggregates = self.analytics.targets_year(year, entity_id)
        by_key = {(row.periodo_mes, row.indicador): row for row in aggregates["rows"]}
        q = by_key.get((month, "CONSULTAS"))
        r = by_key.get((month, "REGISTROS"))
        q_target, q_actual = (q.target, q.actual) if q else (ZERO, ZERO)
        r_target, r_actual = (r.target, r.actual) if r else (ZERO, ZERO)
        if selected == "CONSULTAS":
            meta_total, actual_total = q_target, q_actual
        elif selected == "REGISTROS":
            meta_total, actual_total = r_target, r_actual
        else:
            meta_total, actual_total = q_target + r_target, q_actual + r_actual
        achievement = None if meta_total == 0 else actual_total / meta_total * Decimal("100")
        associations = aggregates["associations"].get(month, ZERO)
        previous = aggregates["associations"].get(month - 1, ZERO)
        variation = None if previous == 0 else associations / previous * Decimal("100") - Decimal("100")
        ticket = None if associations == 0 else actual_total / associations
        ranking = [] if self.ranking is None else self.ranking.quarterly(year, (month - 1) // 3 + 1)
        if entity_id is not None:
            ranking = [row for row in ranking if row.entity_id == entity_id]
        return {
            "year": year, "month": month, "indicator": selected,
            "filters": {"entities": [{"id": row.id, "code": row.codigo_entidade,
                                        "name": row.nome} for row in aggregates["entities"]]},
            "queries": self._target_values(q_target, q_actual),
            "registrations": self._target_values(r_target, r_actual),
            "total": {"target": meta_total, "actual": actual_total,
                      "achievement_percentage": achievement},
            "associations": associations,
            "association_variation_percentage": variation,
            "average_ticket": ticket,
            "ranking": ranking,
            "monthly": [{
                "month": selected_month,
                "queries_target": (by_key.get((selected_month, "CONSULTAS")).target
                                   if by_key.get((selected_month, "CONSULTAS")) else ZERO),
                "queries_actual": (by_key.get((selected_month, "CONSULTAS")).actual
                                   if by_key.get((selected_month, "CONSULTAS")) else ZERO),
                "registrations_target": (by_key.get((selected_month, "REGISTROS")).target
                                         if by_key.get((selected_month, "REGISTROS")) else ZERO),
                "registrations_actual": (by_key.get((selected_month, "REGISTROS")).actual
                                         if by_key.get((selected_month, "REGISTROS")) else ZERO),
            } for selected_month in self._dashboard_months(start_month, end_month)],
        }

    @staticmethod
    def _dashboard_months(
        start_month: int | None, end_month: int | None,
    ) -> range:
        start = 1 if start_month is None else start_month
        end = 12 if end_month is None else end_month
        if not 1 <= start <= 12 or not 1 <= end <= 12:
            raise ValueError("Mês do período do Dashboard inválido.")
        if start > end:
            raise ValueError("O período inicial não pode ser posterior ao período final.")
        return range(start, end + 1)

    @staticmethod
    def _target_values(target: Decimal, actual: Decimal) -> dict:
        return {"target": target, "actual": actual,
                "achievement_percentage": None if target == 0 else actual / target * 100}

    @staticmethod
    def _target_payload(summary) -> dict:
        return {"target": summary.target_total, "actual": summary.actual_total,
                "achievement_percentage": summary.achievement_percentage}
