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
                year, filters.get("boe_entity_id"),
                filters.get("boe_start_month"), filters.get("boe_end_month"),
                start_year=filters.get("boe_start_year"),
                end_year=filters.get("boe_end_year"),
            ),
            "targets": self.get_targets_dashboard(
                year, filters.get("target_entity_id"),
                filters.get("indicator", "TODAS"),
                filters.get("target_start_month"), filters.get("target_end_month"),
                start_year=filters.get("target_start_year"),
                end_year=filters.get("target_end_year"),
                region=filters.get("region"),
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

    def get_financial_dashboard(
        self, year: int, month: int,
        category: str | None = None,
        entry_type: str | None = None,
        *, start_year: int | None = None, start_month: int | None = None,
        end_year: int | None = None, end_month: int | None = None,
    ) -> dict:
        category = category or None
        entry_type = entry_type or None
        explicit_period = any(
            value is not None
            for value in (start_year, start_month, end_year, end_month)
        )
        if explicit_period:
            start_year = year if start_year is None else start_year
            end_year = year if end_year is None else end_year
            start_month = month if start_month is None else start_month
            end_month = month if end_month is None else end_month
        else:
            # Compatibilidade do contrato anterior:
            # carrega os 12 meses para os gráficos, mas os KPIs continuam
            # representando somente o mês selecionado.
            start_year = end_year = year
            start_month, end_month = 1, 12

        periods = self._dashboard_periods(
            start_year, start_month, end_year, end_month
        )
        metric_periods = periods if explicit_period else ((year, month),)

        aggregates = self.analytics.financial_period(
            start_year, start_month, end_year, end_month, category, entry_type
        )
        official = aggregates if not category and not entry_type else self.analytics.financial_period(
            start_year, start_month, end_year, end_month
        )

        balance_service = FinancialBalanceService(
            FinancialBalanceRepository(self.financial_flow.cashflow.repository.session),
            self.financial_flow,
        )
        first_position = balance_service.position(start_year, start_month)
        running_opening = first_position.opening_balance if first_position else None

        monthly = []
        for selected_year, selected_month in periods:
            key = (selected_year, selected_month)
            cash = aggregates["cash"].get(key)
            investment = aggregates["investments"].get(key)
            direct = aggregates["direct"].get(key, ZERO)
            indirect = cash.indirect if cash else ZERO
            expense = cash.expense if cash else ZERO
            applications = investment.applications if investment else ZERO
            redemptions = investment.redemptions if investment else ZERO
            budget = aggregates["budget"][key]

            official_cash = official["cash"].get(key)
            official_investment = official["investments"].get(key)
            official_direct = official["direct"].get(key, ZERO)
            if running_opening is None or official_direct is None:
                opening = bank = None
            else:
                official_indirect = official_cash.indirect if official_cash else ZERO
                official_expense = official_cash.expense if official_cash else ZERO
                official_boe_expense = official_cash.boe_expense if official_cash else ZERO
                official_applications = official_investment.applications if official_investment else ZERO
                official_redemptions = official_investment.redemptions if official_investment else ZERO
                movement = (
                    official_indirect + official_redemptions + official_direct
                    - official_boe_expense - (official_expense - official_boe_expense)
                    - official_applications
                )
                opening, bank = running_opening, running_opening + movement
                running_opening = bank

            monthly.append({
                "year": selected_year,
                "month": selected_month,
                "revenue": direct + indirect,
                "expense": expense,
                "opening_balance": opening,
                "bank_balance": bank,
                "applications": applications,
                "redemptions": redemptions,
                "budgeted_revenue": budget["RECEITA"],
                "actual_revenue": direct + indirect,
                "budgeted_expense": budget["DESPESA"],
                "actual_expense": expense,
            })

        by_period = {
            (row["year"], row["month"]): row
            for row in monthly
        }
        first = monthly[0] if explicit_period else by_period[(year, month)]
        last = monthly[-1] if explicit_period else by_period[(year, month)]

        direct_total = sum(
            (aggregates["direct"].get(p, ZERO) for p in metric_periods), ZERO
        )
        indirect_total = sum(
            (
                aggregates["cash"][p].indirect
                if p in aggregates["cash"] else ZERO
                for p in metric_periods
            ),
            ZERO,
        )
        expense_total = sum(
            (
                aggregates["cash"][p].expense
                if p in aggregates["cash"] else ZERO
                for p in metric_periods
            ),
            ZERO,
        )
        boe_expense_total = sum(
            (
                aggregates["cash"][p].boe_expense
                if p in aggregates["cash"] else ZERO
                for p in metric_periods
            ),
            ZERO,
        )
        applications_total = sum(
            (
                aggregates["investments"][p].applications
                if p in aggregates["investments"] else ZERO
                for p in metric_periods
            ),
            ZERO,
        )
        redemptions_total = sum(
            (
                aggregates["investments"][p].redemptions
                if p in aggregates["investments"] else ZERO
                for p in metric_periods
            ),
            ZERO,
        )
        budgeted_revenue = sum(
            (aggregates["budget"][p]["RECEITA"] for p in metric_periods), ZERO
        )
        budgeted_expense = sum(
            (aggregates["budget"][p]["DESPESA"] for p in metric_periods), ZERO
        )
        actual_revenue = direct_total + indirect_total
        actual_expense = expense_total
        actual_result = actual_revenue - actual_expense
        budgeted_result = budgeted_revenue - budgeted_expense
        variance = actual_result - budgeted_result
        variance_percentage = None if budgeted_result == 0 else variance / abs(budgeted_result) * Decimal("100")

        applied_balance = ZERO
        applied_periods = [
            period for period in official["applied"]
            if period <= (
                (end_year, end_month) if explicit_period else (year, month)
            )
        ]
        if applied_periods:
            applied_base_period = max(applied_periods)
            applied_balance = official["applied"][applied_base_period]
            applied_balance += sum(
                (
                    row.applications - row.redemptions
                    for period, row in official["investments"].items()
                    if applied_base_period < period <= (
                        (end_year, end_month)
                        if explicit_period
                        else (year, month)
                    )
                ),
                ZERO,
            )

        available_periods = (
            set(official["cash"])
            | set(official["investments"])
            | set(official["direct"])
            | set(official["applied"])
        )
        data_available_through = self._data_available_through(
            periods, available_periods
        )

        return {
            "year": end_year, "month": end_month,
            "data_available_through": data_available_through,
            "start_year": start_year, "start_month": start_month,
            "end_year": end_year, "end_month": end_month,
            "filters": {"category": category, "type": entry_type},
            "balance_available": last["bank_balance"] is not None,
            "kpis": {
                "opening_balance": first["opening_balance"],
                "direct_revenue": direct_total,
                "indirect_revenue": indirect_total,
                "total_revenue": actual_revenue,
                "net_revenue": direct_total - boe_expense_total,
                "total_expense": expense_total,
                "applications": applications_total,
                "redemptions": redemptions_total,
                "bank_balance": last["bank_balance"],
                "applied_balance": applied_balance,
            },
            "budget": {
                "budgeted_revenue": budgeted_revenue,
                "actual_revenue": actual_revenue,
                "budgeted_expense": budgeted_expense,
                "actual_expense": actual_expense,
                "result": actual_result,
                "variance": variance,
                "variance_percentage": variance_percentage,
            },
            "monthly": monthly,
            "revenue_distribution": dict(aggregates["distributions"]["revenue"]),
            "expense_distribution": dict(aggregates["distributions"]["expense"]),
        }

    def get_boe_dashboard(
        self, year: int, entity_id: int | None = None,
        start_month: int | None = None, end_month: int | None = None,
        *, start_year: int | None = None, end_year: int | None = None,
    ) -> dict:
        start_year = year if start_year is None else start_year
        end_year = year if end_year is None else end_year
        start_month = 1 if start_month is None else start_month
        end_month = 12 if end_month is None else end_month
        periods = self._dashboard_periods(
            start_year, start_month, end_year, end_month
        )
        aggregates = self.analytics.boe_period(
            start_year, start_month, end_year, end_month, entity_id
        )
        rows = aggregates["rows"]
        queries = sum((row.queries for row in rows), 0)
        total = sum((row.value for row in rows), ZERO)
        entity_totals: dict[tuple[int, int, str], dict[str, object]] = {}
        for row in rows:
            key = (row.id, row.codigo_entidade, row.nome)
            item = entity_totals.setdefault(
                key,
                {"queries": 0, "total_value": ZERO},
            )
            item["queries"] += row.queries
            item["total_value"] += row.value
        monthly = []
        for selected_year, selected_month in periods:
            selected_rows = [row for row in aggregates["rows"]
                             if (row.periodo_ano, row.periodo_mes)
                             == (selected_year, selected_month)]
            monthly.append({"year": selected_year, "month": selected_month,
                            "queries": sum((row.queries for row in selected_rows), 0),
                            "total_value": sum((row.value for row in selected_rows), ZERO)})
        data_available_through = self._data_available_through(
            periods,
            {(row.periodo_ano, row.periodo_mes) for row in rows},
        )

        return {
            "year": end_year,
            "data_available_through": data_available_through,
            "start_year": start_year, "start_month": start_month,
            "end_year": end_year, "end_month": end_month,
            "unit_value": None if queries == 0 else total / queries,
            "queries": queries, "total_value": total,
            "entity_count": len(entity_totals),
            "filters": {"entities": [{"id": item[0], "code": item[1], "name": item[2]}
                                      for item in aggregates["entities"]]},
            "monthly": monthly,
            "entities": [{
                "id": key[0], "code": key[1], "name": key[2],
                "queries": value["queries"],
                "unit_value": (None if value["queries"] == 0
                               else value["total_value"] / value["queries"]),
                "total_value": value["total_value"],
            } for key, value in sorted(entity_totals.items(), key=lambda item: item[0][1])],
        }

    def get_available_years(self) -> dict[str, list[int]]:
        return self.analytics.available_years()

    def get_targets_dashboard(
        self, year: int, entity_id: int | None = None,
        indicator: str = "TODAS",
        start_month: int | None = None, end_month: int | None = None,
        *, start_year: int | None = None, end_year: int | None = None,
        region: str | None = None,
    ) -> dict:
        selected = indicator.upper()
        if selected not in {"CONSULTAS", "REGISTROS", "TODAS"}:
            raise ValueError("Indicador inválido.")
        region = region.upper() if region else None
        if region not in {None, "NORTE", "NOROESTE", "CENTRO", "LESTE", "SUL"}:
            raise ValueError("Região inválida.")
        start_year = year if start_year is None else start_year
        end_year = year if end_year is None else end_year
        start_month = 1 if start_month is None else start_month
        end_month = 12 if end_month is None else end_month
        periods = self._dashboard_periods(
            start_year, start_month, end_year, end_month
        )
        aggregates = self.analytics.targets_period(
            start_year, start_month, end_year, end_month, entity_id, region
        )
        by_key = {
            (row.periodo_ano, row.periodo_mes, row.indicador): row
            for row in aggregates["rows"]
        }
        q_target = sum(
            (by_key[(*period, "CONSULTAS")].target
             for period in periods if (*period, "CONSULTAS") in by_key),
            ZERO,
        )
        q_actual = sum(
            (by_key[(*period, "CONSULTAS")].actual
             for period in periods if (*period, "CONSULTAS") in by_key),
            ZERO,
        )
        r_target = sum(
            (by_key[(*period, "REGISTROS")].target
             for period in periods if (*period, "REGISTROS") in by_key),
            ZERO,
        )
        r_actual = sum(
            (by_key[(*period, "REGISTROS")].actual
             for period in periods if (*period, "REGISTROS") in by_key),
            ZERO,
        )
        if selected == "CONSULTAS":
            meta_total, actual_total = q_target, q_actual
        elif selected == "REGISTROS":
            meta_total, actual_total = r_target, r_actual
        else:
            meta_total, actual_total = q_target + r_target, q_actual + r_actual
        achievement = None if meta_total == 0 else actual_total / meta_total * Decimal("100")
        target_periods = {
            (row.periodo_ano, row.periodo_mes)
            for row in aggregates["rows"]
        }
        association_periods = set(aggregates["associations"])
        available_periods = target_periods | association_periods

        effective_periods = [
            period for period in periods
            if period in available_periods
        ]
        effective_period = max(effective_periods) if effective_periods else None

        effective_association_periods = [
            period for period in periods
            if period in association_periods
        ]
        first_association_period = (
            min(effective_association_periods)
            if effective_association_periods else None
        )
        last_association_period = (
            max(effective_association_periods)
            if effective_association_periods else None
        )

        initial_associations = (
            aggregates["associations"].get(first_association_period, ZERO)
            if first_association_period is not None else ZERO
        )
        associations = (
            aggregates["associations"].get(last_association_period, ZERO)
            if last_association_period is not None else ZERO
        )

        variation = (
            None
            if initial_associations == 0
            else associations / initial_associations * Decimal("100") - Decimal("100")
        )
        ticket = None if associations == 0 else actual_total / associations

        if self.ranking is None or effective_period is None:
            ranking = []
        else:
            ranking_year, ranking_month = effective_period
            ranking = self.ranking.quarterly(
                ranking_year,
                (ranking_month - 1) // 3 + 1,
            )
        if region is not None:
            allowed_ids = {row.id for row in aggregates["entities"]}
            ranking = [row for row in ranking if row.entity_id in allowed_ids]
        if entity_id is not None:
            ranking = [row for row in ranking if row.entity_id == entity_id]
        data_available_through = self._data_available_through(
            periods,
            available_periods,
        )

        return {
            "year": end_year,
            "data_available_through": data_available_through,
            "start_year": start_year, "start_month": start_month,
            "end_year": end_year, "end_month": end_month,
            "indicator": selected, "region": region,
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
                "year": selected_year, "month": selected_month,
                "queries_target": (by_key.get((selected_year, selected_month, "CONSULTAS")).target
                                   if by_key.get((selected_year, selected_month, "CONSULTAS")) else ZERO),
                "queries_actual": (by_key.get((selected_year, selected_month, "CONSULTAS")).actual
                                   if by_key.get((selected_year, selected_month, "CONSULTAS")) else ZERO),
                "registrations_target": (by_key.get((selected_year, selected_month, "REGISTROS")).target
                                         if by_key.get((selected_year, selected_month, "REGISTROS")) else ZERO),
                "registrations_actual": (by_key.get((selected_year, selected_month, "REGISTROS")).actual
                                         if by_key.get((selected_year, selected_month, "REGISTROS")) else ZERO),
            } for selected_year, selected_month in periods],
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
    def _data_available_through(
        periods: tuple[tuple[int, int], ...],
        available_periods: set[tuple[int, int]],
    ) -> dict[str, int] | None:
        available = [
            period for period in periods
            if period in available_periods
        ]
        if not available:
            return None
        latest = max(available)
        if latest >= periods[-1]:
            return None
        return {"year": latest[0], "month": latest[1]}

    @staticmethod
    def _dashboard_periods(
        start_year: int, start_month: int, end_year: int, end_month: int,
    ) -> tuple[tuple[int, int], ...]:
        if not 1 <= start_month <= 12 or not 1 <= end_month <= 12:
            raise ValueError("Os meses do período devem estar entre 1 e 12.")
        if start_year * 100 + start_month > end_year * 100 + end_month:
            raise ValueError("O período inicial deve ser anterior ou igual ao período final.")
        periods = []
        year, month = start_year, start_month
        while (year, month) <= (end_year, end_month):
            periods.append((year, month))
            if month == 12:
                year, month = year + 1, 1
            else:
                month += 1
        return tuple(periods)

    @staticmethod
    def _target_values(target: Decimal, actual: Decimal) -> dict:
        return {"target": target, "actual": actual,
                "achievement_percentage": None if target == 0 else actual / target * 100}

    @staticmethod
    def _target_payload(summary) -> dict:
        return {"target": summary.target_total, "actual": summary.actual_total,
                "achievement_percentage": summary.achievement_percentage}
